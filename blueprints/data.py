"""
blueprints/data.py — core data I/O routes.

Handles: upload, cell editing, column operations, row deletion,
         type casting, and file download.
"""

import io
import os
import tempfile
import traceback

import numpy as np
import pandas as pd
from flask import Blueprint, request, jsonify, send_file

import inputting
import activity_log
from app_state import BASE_DIR
from serializers import json_safe
from blueprints._session import resolve_state


# Built-in teaching datasets: id -> (filename, human label)
EXAMPLE_DATASETS = {
    "clinical_trial": ("clinical_trial.csv", "Clinical Trial (two groups, paired BP, outcome)"),
    "teaching_methods": ("teaching_methods.csv", "Teaching Methods (three groups, exam scores)"),
    "health_survey": ("health_survey.csv", "Health Survey (categorical associations)"),
}


def create_blueprint(store):
    bp = Blueprint('data', __name__)

    def _no_data():
        return jsonify({"error": "No data loaded"}), 400

    # ------------------------------------------------------------------
    # Built-in example datasets (for teaching / quick demos)
    # ------------------------------------------------------------------

    @bp.route('/examples', methods=['GET'])
    def list_examples():
        return jsonify({"examples": [
            {"id": k, "label": v[1]} for k, v in EXAMPLE_DATASETS.items()
        ]})

    @bp.route('/examples/<dataset_id>', methods=['POST'])
    def load_example(dataset_id):
        from flask import current_app
        app_state = resolve_state(store)
        entry = EXAMPLE_DATASETS.get(dataset_id)
        if entry is None:
            return jsonify({"error": "Unknown example dataset"}), 404
        path = os.path.join(BASE_DIR, 'examples', entry[0])
        if not os.path.exists(path):
            return jsonify({"error": "Example dataset file is missing."}), 500
        try:
            df = inputting.read_dataframe(path)
            app_state.load(df, name=f"example:{dataset_id}")
            payload = app_state.get_table_data()
            payload["imputation_metadata"] = []
            payload["quarantined_cols"] = []
            params = request.get_json(silent=True) or {}
            activity_log.record(action="load_example", method=dataset_id,
                                payload={"rows": len(df), "columns": list(df.columns)},
                                session_id=params.get("session_id"))
            return jsonify(payload)
        except Exception:
            current_app.logger.exception("Failed to load example %s", dataset_id)
            return jsonify({"error": "Could not load that example dataset."}), 500

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    @bp.route('/new-blank', methods=['POST'])
    def new_blank_dataset():
        """Create an empty, editable dataset with the requested shape so the
        user can type values directly into the grid (Excel-style entry)."""
        from flask import current_app
        app_state = resolve_state(store)
        params = request.get_json(silent=True) or {}
        try:
            n_rows = int(params.get('rows', 10))
            n_cols = int(params.get('cols', 3))
        except (TypeError, ValueError):
            return jsonify({"error": "Rows and columns must be whole numbers."}), 400
        n_rows = max(1, min(n_rows, 10000))
        n_cols = max(1, min(n_cols, 100))

        col_names = params.get('column_names') or []
        columns = []
        seen = set()
        for i in range(n_cols):
            name = (col_names[i].strip() if i < len(col_names) and col_names[i] else '') or f"var{i+1}"
            # de-duplicate
            base, k = name, 1
            while name in seen:
                k += 1
                name = f"{base}_{k}"
            seen.add(name)
            columns.append(name)

        try:
            df = pd.DataFrame({c: [None] * n_rows for c in columns}, columns=columns)
            app_state.load(df, name="blank")
            payload = app_state.get_table_data()
            payload["imputation_metadata"] = []
            payload["quarantined_cols"] = []
            activity_log.record(action="new_blank",
                                method=f"{n_rows}x{n_cols}",
                                payload={"columns": columns},
                                session_id=params.get("session_id"))
            return jsonify(payload)
        except Exception:
            current_app.logger.exception("Failed to create blank dataset")
            return jsonify({"error": "Could not create a blank dataset."}), 500

    @bp.route('/upload', methods=['POST'])
    def upload_file():
        app_state = resolve_state(store)
        from flask import current_app
        if 'file' not in request.files:
            current_app.logger.error("Upload failed: no 'file' in request")
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']
        filename = file.filename or ''
        current_app.logger.info("Upload: filename=%s", filename)

        if not filename:
            return jsonify({"error": "Empty filename"}), 400

        suffix = os.path.splitext(filename)[1]
        tmp_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name

            df = inputting.read_dataframe(tmp_path)

            # Treat an empty/headerless/garbage parse as a client error, not a
            # server crash. read_dataframe may return None/empty or raise on junk.
            if df is None or getattr(df, "empty", True) or df.shape[1] == 0:
                return jsonify({
                    "error": "Could not read any tabular data from that file. "
                             "Please upload a non-empty CSV/Excel file with a header row."
                }), 400

            current_app.logger.info("Loaded: shape=%s", df.shape)

            inf_counts = {}
            for col in df.columns:
                try:
                    if pd.api.types.is_numeric_dtype(df[col]):
                        count = int(np.isinf(df[col].to_numpy(dtype=float, na_value=np.nan)).sum())
                        if count:
                            inf_counts[col] = count
                except Exception:
                    continue
            if inf_counts:
                current_app.logger.warning("Infinity values: %s", inf_counts)

            app_state.load(df, name=filename)
            payload = app_state.get_table_data()
            payload["imputation_metadata"] = []
            payload["quarantined_cols"] = []
            activity_log.record(action="upload", method=filename,
                                payload={"rows": int(df.shape[0]), "columns": list(df.columns)},
                                session_id=request.form.get("session_id"))
            return jsonify(payload)

        except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError,
                UnicodeDecodeError, UnicodeError) as e:
            # Bad/unreadable input → client error. No traceback in the body.
            current_app.logger.info("Rejected unparseable upload %s: %s", filename, e)
            return jsonify({
                "error": "Could not parse that file. Please check it is a valid "
                         "CSV or Excel file with a header row.",
            }), 400

        except Exception:
            # Genuine server fault. Log it (with traceback via .exception), but
            # never leak internals to the client.
            current_app.logger.exception("Unexpected upload failure: %s", filename)
            return jsonify({"error": "An unexpected error occurred while reading the file."}), 500

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Cell editing
    # ------------------------------------------------------------------

    @bp.route('/update-cell', methods=['POST'])
    def update_cell():
        app_state = resolve_state(store)
        if not app_state.has_data:
            return _no_data()
        try:
            data = request.json
            row_idx = data['row']
            col_idx = data['col']
            new_val = data['newValue']
            force_change = data.get('force', False)

            if new_val == "" or new_val is None:
                new_val = np.nan

            col_name = app_state.current_df.columns[col_idx]

            if pd.api.types.is_numeric_dtype(app_state.current_df[col_name]) and pd.notna(new_val):
                try:
                    parsed = float(new_val)
                    if pd.api.types.is_integer_dtype(app_state.current_df[col_name]):
                        if parsed.is_integer():
                            new_val = int(parsed)
                        else:
                            app_state.current_df[col_name] = app_state.current_df[col_name].astype(float)
                            new_val = parsed
                    else:
                        new_val = parsed
                except ValueError:
                    if not force_change:
                        return jsonify({
                            "status": "confirm_type_change",
                            "message": (
                                f"You entered text ('{new_val}') into the numeric column "
                                f"'{col_name}'. This will permanently convert the entire "
                                f"column to text. Proceed?"
                            ),
                        }), 200
                    app_state.current_df[col_name] = app_state.current_df[col_name].astype(object)

            app_state.current_df.iloc[row_idx, col_idx] = new_val

            # Manual-entry convenience: if this column is still text/object (e.g.
            # it began as a blank dataset) but every non-empty value now parses
            # as a number, promote it to numeric so analyses can use it without a
            # separate "cast column" step. A single non-numeric entry leaves it
            # as text.
            try:
                col_series = app_state.current_df[col_name]
                if col_series.dtype == object:
                    non_null = col_series.dropna()
                    if len(non_null) > 0:
                        coerced = pd.to_numeric(non_null, errors='coerce')
                        if coerced.notna().all():
                            app_state.current_df[col_name] = pd.to_numeric(
                                col_series, errors='coerce'
                            )
            except Exception:
                pass

            app_state.rebuild_exclusion_state()
            return jsonify(app_state.merge_exclusion_payload({
                "status": "success",
                "new_dtype": str(app_state.current_df[col_name].dtype),
            }))

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ------------------------------------------------------------------
    # Column operations
    # ------------------------------------------------------------------

    @bp.route('/update-column', methods=['POST'])
    def update_column():
        app_state = resolve_state(store)
        if not app_state.has_data:
            return _no_data()

        data = request.get_json()
        action = data.get('action')

        if action == 'rename':
            old_name = data['oldName']
            new_name = (data['newName'] or '').strip()
            if not old_name or old_name not in app_state.current_df.columns:
                return jsonify({"error": "Invalid source column for rename."}), 400
            if not new_name:
                return jsonify({"error": "New column name cannot be empty."}), 400
            if new_name != old_name and new_name in app_state.current_df.columns:
                return jsonify({"error": f"A column named '{new_name}' already exists."}), 400
            app_state.current_df.rename(columns={old_name: new_name}, inplace=True)
            for rule in app_state.filter_rules:
                if rule.get('column') == old_name:
                    rule['column'] = new_name

        elif action == 'add':
            insert_index = data['index']
            col_name = (data['name'] or '').strip()
            if not col_name:
                return jsonify({"error": "Column name cannot be empty."}), 400
            if col_name in app_state.current_df.columns:
                return jsonify({"error": f"A column named '{col_name}' already exists."}), 400
            if not isinstance(insert_index, int) or not (0 <= insert_index <= len(app_state.current_df.columns)):
                return jsonify({"error": "Invalid insert index."}), 400
            app_state.current_df.insert(loc=insert_index, column=col_name, value=pd.NA)

        elif action == 'remove':
            removed_name = data.get('name')
            if not removed_name or removed_name not in app_state.current_df.columns:
                return jsonify({"error": "Invalid column for removal."}), 400
            app_state.current_df.drop(columns=[removed_name], inplace=True)
            app_state.filter_rules = [
                r for r in app_state.filter_rules if r.get('column') != removed_name
            ]

        elif action == 'remove_multiple':
            removed_names = data.get('names', [])
            if not isinstance(removed_names, list) or not removed_names:
                return jsonify({"error": "No columns provided for removal."}), 400
            missing = [n for n in removed_names if n not in app_state.current_df.columns]
            if missing:
                return jsonify({"error": f"Some columns not found: {', '.join(missing)}"}), 400
            app_state.current_df.drop(columns=removed_names, inplace=True)
            removed_set = set(removed_names)
            app_state.filter_rules = [
                r for r in app_state.filter_rules if r.get('column') not in removed_set
            ]

        else:
            return jsonify({"error": f"Unknown column action: {action}"}), 400

        app_state.rebuild_exclusion_state()
        return jsonify({"success": True, **app_state.get_table_data()})

    # ------------------------------------------------------------------
    # Row deletion
    # ------------------------------------------------------------------

    @bp.route('/delete-rows', methods=['POST'])
    def delete_rows():
        app_state = resolve_state(store)
        if not app_state.has_data:
            return _no_data()
        from flask import current_app

        data = request.get_json() or {}
        indices = data.get('indices', [])
        if not isinstance(indices, list) or not indices:
            return jsonify({"error": "No row indices provided."}), 400

        max_index = len(app_state.current_df) - 1
        out_of_range = [i for i in indices if not isinstance(i, int) or i < 0 or i > max_index]
        if out_of_range:
            return jsonify({"error": f"Row indices out of range: {out_of_range}"}), 400

        app_state.current_df = (
            app_state.current_df
            .drop(app_state.current_df.index[indices])
            .reset_index(drop=True)
        )
        app_state.rebuild_exclusion_state()
        current_app.logger.info("Deleted %d row(s). New shape: %s", len(indices), app_state.current_df.shape)
        return jsonify({"success": True, **app_state.get_table_data()})

    # ------------------------------------------------------------------
    # Type casting
    # ------------------------------------------------------------------

    @bp.route('/cast-column', methods=['POST'])
    def cast_column():
        app_state = resolve_state(store)
        if not app_state.has_data:
            return _no_data()

        data = request.get_json()
        col_name, new_type = data['name'], data['new_type']

        if new_type == 'numeric':
            app_state.current_df[col_name] = pd.to_numeric(
                app_state.current_df[col_name], errors='coerce'
            ).astype(float)
        elif new_type == 'integer':
            app_state.current_df[col_name] = pd.to_numeric(
                app_state.current_df[col_name], errors='coerce'
            ).astype('Int64')
        elif new_type == 'text':
            app_state.current_df[col_name] = app_state.current_df[col_name].astype("string")

        app_state.rebuild_exclusion_state()
        return jsonify(app_state.merge_exclusion_payload({
            "success": True,
            "new_dtype": str(app_state.current_df[col_name].dtype),
            "column_data": app_state.current_df[col_name].astype(object).replace({pd.NA: None}).tolist(),
        }))

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    @bp.route('/download', methods=['GET'])
    def download_file():
        app_state = resolve_state(store)
        if not app_state.has_data:
            return _no_data()

        file_type = request.args.get('type', 'csv')
        filename = request.args.get('filename', 'data')
        output = io.BytesIO()

        if file_type == 'xlsx':
            app_state.current_df.to_excel(output, index=False)
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f'{filename}.xlsx'
        else:
            app_state.current_df.to_csv(output, index=False)
            mimetype = 'text/csv'
            filename = f'{filename}.csv'

        output.seek(0)
        return send_file(output, mimetype=mimetype, download_name=filename, as_attachment=True)

    @bp.route('/download-report', methods=['POST'])
    def download_report():
        app_state = resolve_state(store)
        data = request.get_json()
        filename = data.get('filename', 'report.xlsx')
        tables = data.get('tables', {})
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for sheet_name, table_data in tables.items():
                if table_data and table_data.get('headers') and table_data.get('data'):
                    df = pd.DataFrame(table_data['data'], columns=table_data['headers'])
                    df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            download_name=filename,
            as_attachment=True,
        )

    return bp
