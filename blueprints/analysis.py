"""
blueprints/analysis.py — statistical analysis routes (trimmed build).

Handles: correlation (+ heatmap) and the basic individual test methods
(t-tests, Mann-Whitney, Wilcoxon, ANOVA, Kruskal-Wallis, chi-square, Fisher).
"""

import correlation
import description
import plots
import activity_log
import code_gen
from flask import Blueprint, request, jsonify, current_app

from individual_methods import METHODS
from serializers import json_safe, df_to_json
from blueprints._session import resolve_state


def _sanitize_payload(payload):
    """Clean a request payload coming from the UI before it reaches analysis
    code. Multi-selects in the parameter modal include a "None" option whose
    value is an empty string, so an unselected multi-select arrives as [""].
    Left alone, [""] is a non-empty list containing a bogus column name and
    breaks methods that should treat "nothing selected" as "use all columns".

    For every list value we drop blank/None entries; if the list becomes empty
    the key is removed so downstream `.get(key)` returns None and the natural
    "all columns" fallback applies. Scalar values are left untouched, since a
    blank text field (e.g. GOF expected-frequencies left empty for "uniform")
    can be meaningful.
    """
    if not isinstance(payload, dict):
        return payload
    cleaned = {}
    for key, value in payload.items():
        if isinstance(value, list):
            filtered = [v for v in value
                        if not (v is None or (isinstance(v, str) and v.strip() == ''))]
            if filtered:
                cleaned[key] = filtered
            # else: drop the key entirely so it reads as "not provided"
        else:
            cleaned[key] = value
    return cleaned


def create_blueprint(store):
    bp = Blueprint('analysis', __name__)

    def _no_data():
        return jsonify({"error": "No data loaded"}), 400

    def _client_error_message(e):
        if isinstance(e, KeyError):
            return f"Unknown or missing field/column: {e.args[0]!r}" if e.args else "Missing required field."
        return str(e)

    # ------------------------------------------------------------------
    # Description
    # ------------------------------------------------------------------

    @bp.route('/description/numerical-qc', methods=['POST'])
    def run_numerical_qc_endpoint():
        app_state = resolve_state(store)
        if not app_state.has_data:
            return jsonify({"error": "No data to analyze"}), 400
        try:
            report = description.qc_numerical_dataframe(app_state.get_active_df())
            payload = _sanitize_payload(request.get_json(silent=True) or {})
            activity_log.record(action="numerical_qc", method="numerical_qc",
                                session_id=payload.get("session_id"))
            return jsonify(report)
        except (ValueError, KeyError) as e:
            current_app.logger.info("Bad analysis request: %s", e)
            return jsonify({"error": _client_error_message(e)}), 400
        except Exception:
            current_app.logger.exception("Unexpected analysis error")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @bp.route('/description/describe', methods=['POST'])
    def describe_endpoint():
        app_state = resolve_state(store)
        if not app_state.has_data:
            return _no_data()

        params = _sanitize_payload(request.get_json() or {})
        group_columns = [col for col in params.get('group_columns', []) if col]
        df = app_state.get_active_df()

        try:
            if group_columns:
                result_dict = description.describe_by_groups(df, group_columns)
            else:
                result_dict = description.describe_df(df)

            json_results = {
                key: df_to_json(df_part)
                for key, df_part in result_dict.items()
                if df_part is not None
            }
            activity_log.record(
                action="describe",
                method="describe_by_groups" if group_columns else "describe",
                payload=params,
                result={"tables": json_results},
                session_id=params.get("session_id"),
            )
            return jsonify({
                "tables": json_results,
                "filter_summary": app_state.get_exclusion_payload()['filter_summary'],
            })
        except (ValueError, KeyError) as e:
            current_app.logger.info("Bad analysis request: %s", e)
            return jsonify({"error": _client_error_message(e)}), 400
        except Exception:
            current_app.logger.exception("Unexpected analysis error")
            return jsonify({"error": "An unexpected error occurred."}), 500

    # ------------------------------------------------------------------
    # Correlation
    # ------------------------------------------------------------------

    @bp.route('/analysis/correlation', methods=['POST'])
    def run_correlation():
        app_state = resolve_state(store)
        if not app_state.has_data:
            return _no_data()

        params = _sanitize_payload(request.get_json() or {})
        method = params.get('method', 'pearson')
        columns = params.get('columns') or None
        df = app_state.get_active_df()

        try:
            result = correlation.run(method, df, columns=columns)
            result['filter_summary'] = app_state.get_exclusion_payload()['filter_summary']

            # Auto-generate heatmap — never breaks the main result
            try:
                matrix_table = result.get('matrix')
                if matrix_table and matrix_table.get('headers') and matrix_table.get('data'):
                    heatmap_fig = plots.correlation_heatmap(
                        matrix_table, result.get('method_name', method)
                    )
                    heatmap_fig.update_layout(title_x=0.5)
                    result.setdefault('plotly_figures', {})['Heatmap'] = heatmap_fig.to_dict()
            except Exception:
                pass

            activity_log.record(
                action="correlation",
                method=method,
                payload=params,
                result=result,
                session_id=params.get("session_id"),
                dataset=getattr(app_state, "dataset_name", None),
                n_rows=int(df.shape[0]) if df is not None else None,
            )
            try:
                result['python_code'] = code_gen.generate(method, params)
            except Exception:
                pass
            return jsonify(json_safe(result))
        except (ValueError, KeyError) as e:
            current_app.logger.info("Bad analysis request: %s", e)
            return jsonify({"error": _client_error_message(e)}), 400
        except Exception:
            current_app.logger.exception("Unexpected analysis error")
            return jsonify({"error": "An unexpected error occurred."}), 500

    # ------------------------------------------------------------------
    # Individual / tests methods (all light, synchronous)
    # ------------------------------------------------------------------

    # Methods that can run without a loaded dataset (user supplies the numbers).
    DATA_OPTIONAL_METHODS = {'chi_square_gof', 'chi-square-gof'}

    @bp.route("/analysis/individual/<method>", methods=["POST"])
    @bp.route("/analysis/tests/<method>", methods=["POST"])
    @bp.route("/analysis/smart/<method>", methods=["POST"])
    def run_analysis_method(method):
        app_state = resolve_state(store)
        payload = _sanitize_payload(request.get_json() or {})

        if method not in METHODS:
            return jsonify({"error": f"Unknown method: {method}"}), 404

        data_optional = method in DATA_OPTIONAL_METHODS
        # Manual GOF (entering observed frequencies) needs no dataset. Column
        # mode still requires data, so only the explicit 'manual' mode is exempt.
        manual_no_data = data_optional and payload.get('mode') == 'manual'

        if not app_state.has_data and not manual_no_data:
            return _no_data()

        df = app_state.get_active_df() if app_state.has_data else None
        try:
            result = METHODS[method](payload, df)
            if isinstance(result, dict) and app_state.has_data:
                result = app_state.merge_exclusion_payload(result)
            if isinstance(result, dict):
                try:
                    result['python_code'] = code_gen.generate(method, payload)
                except Exception:
                    pass
            activity_log.record(
                action="analysis",
                method=method,
                payload=payload,
                result=result,
                session_id=payload.get("session_id"),
                dataset=getattr(app_state, "dataset_name", None),
                n_rows=(int(df.shape[0]) if df is not None else None),
            )
            return jsonify(json_safe(result))
        except (ValueError, KeyError) as e:
            current_app.logger.info("Bad analysis request: %s", e)
            return jsonify({"error": _client_error_message(e)}), 400
        except Exception:
            current_app.logger.exception("Unexpected analysis error")
            return jsonify({"error": "An unexpected error occurred."}), 500

    @bp.route("/analysis/hosted-methods")
    def hosted_methods():
        return jsonify({"methods": sorted(set(METHODS.keys()))})

    return bp
