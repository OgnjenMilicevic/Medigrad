"""
blueprints/help_bp.py — help system routes.

No state dependency — serves static markdown files and manifests.
"""

import json
import os
import re
import traceback

import markdown
from flask import Blueprint, jsonify

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_blueprint():
    bp = Blueprint('help', __name__)
    help_dir = os.path.join(BASE_DIR, 'help_content')

    @bp.route('/help/init')
    def get_help_init_data():
        glossary = {}
        help_structure = []
        try:
            glossary_path = os.path.join(help_dir, 'glossary.json')
            if os.path.exists(glossary_path):
                with open(glossary_path, 'r', encoding='utf-8') as f:
                    glossary = json.load(f)

            manifest_path = os.path.join(help_dir, 'manifest.json')
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                    help_structure = manifest.get('help_structure', [])

            return jsonify({"help_structure": help_structure, "glossary": glossary})
        except Exception as e:
            print(traceback.format_exc())
            return jsonify({"error": str(e)}), 500

    @bp.route('/help/<page_name>')
    def get_help_page(page_name):
        if '..' in page_name or '/' in page_name:
            return jsonify({"error": "Invalid help page name"}), 400

        glossary = {}
        glossary_path = os.path.join(help_dir, 'glossary.json')
        if os.path.exists(glossary_path):
            with open(glossary_path, 'r', encoding='utf-8') as f:
                glossary = json.load(f)

        def resolve_and_replace(match):
            term = match.group(1).lower()
            original_text = match.group(1)
            definition = glossary.get(term, "Definition not found.")
            if definition in glossary:
                definition = glossary[definition]
            return f'<span class="tooltip" data-tooltip="{definition}">{original_text}</span>'

        file_path = os.path.join(help_dir, f'{page_name}.md')
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content_md = f.read()
            processed_md = re.sub(r'\[\[([^\]]+)\]\]', resolve_and_replace, content_md)
            html_content = markdown.markdown(processed_md)
            return jsonify({"html_content": html_content})
        except FileNotFoundError:
            return jsonify({"error": f"Help page '{page_name}.md' not found."}), 404
        except Exception as e:
            print(traceback.format_exc())
            return jsonify({"error": str(e)}), 500

    return bp
