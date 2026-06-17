"""
blueprints/mfub_bp.py — university/department materials tab (MFUB).

Serves a manifest of course materials plus their content. Instructors add
files to the `mfub/` folder and list them in `mfub/manifest.json`; the items
then appear in the app's MFUB menu. Supports three item types:
  - markdown : rendered to HTML and shown in a report dialog
  - file     : any document (PDF, pptx, image, …), served for view/download
  - link     : an external URL (handled entirely on the front end)
"""

import json
import os

from flask import Blueprint, jsonify, send_from_directory, abort

from app_state import BASE_DIR

MFUB_DIR = os.path.join(BASE_DIR, 'mfub')


def _safe_path(filename):
    """Resolve a filename inside MFUB_DIR, blocking path traversal."""
    full = os.path.normpath(os.path.join(MFUB_DIR, filename))
    if not full.startswith(os.path.normpath(MFUB_DIR) + os.sep):
        abort(403)
    return full


def create_blueprint():
    bp = Blueprint('mfub', __name__)

    @bp.route('/mfub/manifest')
    def mfub_manifest():
        path = os.path.join(MFUB_DIR, 'manifest.json')
        if not os.path.exists(path):
            return jsonify({"title": "MFUB", "intro": "", "items": []})
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        except Exception:
            return jsonify({"title": "MFUB", "intro": "Could not read manifest.", "items": []})

    @bp.route('/mfub/markdown/<path:filename>')
    def mfub_markdown(filename):
        path = _safe_path(filename)
        if not os.path.exists(path):
            return jsonify({"error": "Material not found."}), 404
        try:
            import markdown
            with open(path, 'r', encoding='utf-8') as f:
                md = f.read()
            html = markdown.markdown(md, extensions=['tables', 'fenced_code'])
            return jsonify({"html": html})
        except Exception:
            return jsonify({"error": "Could not render material."}), 500

    @bp.route('/mfub/file/<path:filename>')
    def mfub_file(filename):
        path = _safe_path(filename)
        if not os.path.exists(path):
            abort(404)
        return send_from_directory(MFUB_DIR, filename)

    return bp
