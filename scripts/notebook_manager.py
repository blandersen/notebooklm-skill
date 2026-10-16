#!/usr/bin/env python3
"""
Notebook Library Management for NotebookLM
Manages a library of NotebookLM notebooks with metadata
Based on the MCP server implementation
"""

import json
import re
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from config import LIBRARY_FILE, normalize_notebook_url


def slugify(name: str) -> str:
    """Shell-safe ID: lowercase alphanumerics separated by single hyphens"""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "notebook"


class NotebookLibrary:
    """Manages a collection of NotebookLM notebooks with metadata"""

    def __init__(self):
        """Initialize the notebook library"""
        self.library_file = LIBRARY_FILE
        self.library_file.parent.mkdir(parents=True, exist_ok=True)
        self.notebooks: Dict[str, Dict[str, Any]] = {}
        self.active_notebook_id: Optional[str] = None

        # Load existing library
        self._load_library()

    def _load_library(self):
        """Load library from disk"""
        if self.library_file.exists():
            try:
                with open(self.library_file, 'r') as f:
                    data = json.load(f)
                    self.notebooks = data.get('notebooks', {})
                    self.active_notebook_id = data.get('active_notebook_id')
                self._migrate()
            except Exception as e:
                print(f"⚠️ Error loading library: {e}")
                self.notebooks = {}
                self.active_notebook_id = None
        else:
            self._save_library()

    def _migrate(self):
        """Re-key legacy IDs (which could contain ':' or '&') and canonicalize URLs"""
        changed = False
        migrated = {}
        for old_id, notebook in self.notebooks.items():
            new_id = slugify(old_id)
            if new_id in migrated:
                new_id = old_id  # keep legacy ID rather than collide
            if new_id != old_id:
                notebook['legacy_id'] = old_id
                if self.active_notebook_id == old_id:
                    self.active_notebook_id = new_id
                changed = True
            notebook['id'] = new_id
            try:
                url = normalize_notebook_url(notebook['url'])
                if url != notebook['url']:
                    notebook['url'] = url
                    changed = True
            except ValueError:
                pass
            migrated[new_id] = notebook
        self.notebooks = migrated
        if changed:
            self._save_library()

    def _save_library(self):
        """Save library to disk"""
        try:
            data = {
                'notebooks': self.notebooks,
                'active_notebook_id': self.active_notebook_id,
                'updated_at': datetime.now().isoformat()
            }
            with open(self.library_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"❌ Error saving library: {e}")

    def add_notebook(
        self,
        url: str,
        name: str,
        description: str,
        topics: List[str],
        content_types: Optional[List[str]] = None,
        use_cases: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Add a new notebook to the library

        Args:
            url: NotebookLM notebook URL
            name: Display name for the notebook
            description: What's in this notebook
            topics: Topics covered
            content_types: Types of content (optional)
            use_cases: When to use this notebook (optional)
            tags: Additional tags for organization (optional)

        Returns:
            The created notebook object
        """
        url = normalize_notebook_url(url)
        notebook_id = slugify(name)

        for existing in self.notebooks.values():
            if existing['url'] == url:
                raise ValueError(f"URL already in library as '{existing['id']}'")

        # Check for duplicates
        if notebook_id in self.notebooks:
            raise ValueError(f"Notebook with ID '{notebook_id}' already exists")

        # Create notebook object
        notebook = {
            'id': notebook_id,
            'url': url,
            'name': name,
            'description': description,
            'topics': topics,
            'content_types': content_types or [],
            'use_cases': use_cases or [],
            'tags': tags or [],
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'use_count': 0,
            'last_used': None
        }

        # Add to library
        self.notebooks[notebook_id] = notebook

        # Set as active if it's the first notebook
        if len(self.notebooks) == 1:
            self.active_notebook_id = notebook_id

        self._save_library()

        print(f"✅ Added notebook: {name} ({notebook_id})")
        return notebook

    def remove_notebook(self, notebook_id: str) -> bool:
        """
        Remove a notebook from the library

        Args:
            notebook_id: ID of notebook to remove

        Returns:
            True if removed, False if not found
        """
        notebook_id = self.resolve_id(notebook_id) or notebook_id
        if notebook_id in self.notebooks:
            del self.notebooks[notebook_id]

            # Clear active if it was removed
            if self.active_notebook_id == notebook_id:
                self.active_notebook_id = None
                # Set new active if there are other notebooks
                if self.notebooks:
                    self.active_notebook_id = list(self.notebooks.keys())[0]

            self._save_library()
            print(f"✅ Removed notebook: {notebook_id}")
            return True

        print(f"⚠️ Notebook not found: {notebook_id}")
        return False

    def update_notebook(
        self,
        notebook_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        topics: Optional[List[str]] = None,
        content_types: Optional[List[str]] = None,
        use_cases: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update notebook metadata

        Args:
            notebook_id: ID of notebook to update
            Other args: Fields to update (None = keep existing)

        Returns:
            Updated notebook object
        """
        if notebook_id not in self.notebooks:
            raise ValueError(f"Notebook not found: {notebook_id}")

        notebook = self.notebooks[notebook_id]

        # Update fields if provided
        if name is not None:
            notebook['name'] = name
        if description is not None:
            notebook['description'] = description
        if topics is not None:
            notebook['topics'] = topics
        if content_types is not None:
            notebook['content_types'] = content_types
        if use_cases is not None:
            notebook['use_cases'] = use_cases
        if tags is not None:
            notebook['tags'] = tags
        if url is not None:
            notebook['url'] = normalize_notebook_url(url)

        notebook['updated_at'] = datetime.now().isoformat()

        self._save_library()
        print(f"✅ Updated notebook: {notebook['name']}")
        return notebook

    def resolve_id(self, notebook_id: str) -> Optional[str]:
        """Accept current IDs, legacy IDs, or names typed loosely"""
        if notebook_id in self.notebooks:
            return notebook_id
        slug = slugify(notebook_id)
        if slug in self.notebooks:
            return slug
        for nid, notebook in self.notebooks.items():
            if notebook.get('legacy_id') == notebook_id:
                return nid
        return None

    def get_notebook(self, notebook_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific notebook by ID"""
        nid = self.resolve_id(notebook_id)
        return self.notebooks.get(nid) if nid else None

    def list_notebooks(self) -> List[Dict[str, Any]]:
        """List all notebooks in the library"""
        return list(self.notebooks.values())

    def search_notebooks(self, query: str) -> List[Dict[str, Any]]:
        """
        Search notebooks by query

        Args:
            query: Search query (searches name, description, topics, tags)

        Returns:
            List of matching notebooks
        """
        query_lower = query.lower()
        results = []

        for notebook in self.notebooks.values():
            # Search in various fields
            searchable = [
                notebook['name'].lower(),
                notebook['description'].lower(),
                ' '.join(notebook['topics']).lower(),
                ' '.join(notebook['tags']).lower(),
                ' '.join(notebook.get('use_cases', [])).lower()
            ]

            if any(query_lower in field for field in searchable):
                results.append(notebook)

        return results

    def select_notebook(self, notebook_id: str) -> Dict[str, Any]:
        """
        Set a notebook as active

        Args:
            notebook_id: ID of notebook to activate

        Returns:
            The activated notebook
        """
        notebook_id = self.resolve_id(notebook_id)
        if notebook_id is None:
            raise ValueError("Notebook not found")

        self.active_notebook_id = notebook_id
        self._save_library()

        notebook = self.notebooks[notebook_id]
        print(f"✅ Activated notebook: {notebook['name']}")
        return notebook

    def get_active_notebook(self) -> Optional[Dict[str, Any]]:
        """Get the currently active notebook"""
        if self.active_notebook_id:
            return self.notebooks.get(self.active_notebook_id)
        return None

    def increment_use_count(self, notebook_id: str) -> Dict[str, Any]:
        """
        Increment usage counter for a notebook

        Args:
            notebook_id: ID of notebook that was used

        Returns:
            Updated notebook
        """
        if notebook_id not in self.notebooks:
            raise ValueError(f"Notebook not found: {notebook_id}")

        notebook = self.notebooks[notebook_id]
        notebook['use_count'] += 1
        notebook['last_used'] = datetime.now().isoformat()

        self._save_library()
        return notebook

    def get_stats(self) -> Dict[str, Any]:
        """Get library statistics"""
        total_notebooks = len(self.notebooks)
        total_topics = set()
        total_use_count = 0

        for notebook in self.notebooks.values():
            total_topics.update(notebook['topics'])
            total_use_count += notebook['use_count']

        # Find most used
        most_used = None
        if self.notebooks:
            most_used = max(
                self.notebooks.values(),
                key=lambda n: n['use_count']
            )

        return {
            'total_notebooks': total_notebooks,
            'total_topics': len(total_topics),
            'total_use_count': total_use_count,
            'active_notebook': self.get_active_notebook(),
            'most_used_notebook': most_used,
            'library_path': str(self.library_file)
        }


def main():
    """Command-line interface for notebook management"""
    parser = argparse.ArgumentParser(description='Manage NotebookLM library')

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Add command
    add_parser = subparsers.add_parser('add', help='Add a notebook')
    add_parser.add_argument('--url', required=True, help='NotebookLM URL')
    add_parser.add_argument('--name', required=True, help='Display name')
    add_parser.add_argument('--description', required=True, help='Description')
    add_parser.add_argument('--topics', required=True, help='Comma-separated topics')
    add_parser.add_argument('--use-cases', help='Comma-separated use cases')
    add_parser.add_argument('--tags', help='Comma-separated tags')

    # List command
    subparsers.add_parser('list', help='List all notebooks')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search notebooks')
    search_parser.add_argument('--query', required=True, help='Search query')

    # Activate command
    activate_parser = subparsers.add_parser('activate', help='Set active notebook')
    activate_parser.add_argument('--id', required=True, help='Notebook ID')

    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove a notebook')
    remove_parser.add_argument('--id', required=True, help='Notebook ID')

    # Stats command
    subparsers.add_parser('stats', help='Show library statistics')

    args = parser.parse_args()

    # Initialize library
    library = NotebookLibrary()

    # Execute command
    if args.command == 'add':
        topics = [t.strip() for t in args.topics.split(',')]
        use_cases = [u.strip() for u in args.use_cases.split(',')] if args.use_cases else None
        tags = [t.strip() for t in args.tags.split(',')] if args.tags else None

        try:
            notebook = library.add_notebook(
                url=args.url,
                name=args.name,
                description=args.description,
                topics=topics,
                use_cases=use_cases,
                tags=tags
            )
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)
        print(json.dumps(notebook, indent=2))

    elif args.command == 'list':
        notebooks = library.list_notebooks()
        if notebooks:
            print("\n📚 Notebook Library:")
            for notebook in notebooks:
                active = " [ACTIVE]" if notebook['id'] == library.active_notebook_id else ""
                print(f"\n  📓 {notebook['name']}{active}")
                print(f"     ID: {notebook['id']}")
                print(f"     Topics: {', '.join(notebook['topics'])}")
                print(f"     Uses: {notebook['use_count']}")
        else:
            print("📚 Library is empty. Add notebooks with: notebook_manager.py add")

    elif args.command == 'search':
        results = library.search_notebooks(args.query)
        if results:
            print(f"\n🔍 Found {len(results)} notebooks:")
            for notebook in results:
                print(f"\n  📓 {notebook['name']} ({notebook['id']})")
                print(f"     {notebook['description']}")
        else:
            print(f"🔍 No notebooks found for: {args.query}")

    elif args.command == 'activate':
        try:
            notebook = library.select_notebook(args.id)
        except ValueError as e:
            print(f"❌ {e}: {args.id}")
            sys.exit(1)
        print(f"Now using: {notebook['name']}")

    elif args.command == 'remove':
        if library.remove_notebook(args.id):
            print("Notebook removed from library")

    elif args.command == 'stats':
        stats = library.get_stats()
        print("\n📊 Library Statistics:")
        print(f"  Total notebooks: {stats['total_notebooks']}")
        print(f"  Total topics: {stats['total_topics']}")
        print(f"  Total uses: {stats['total_use_count']}")
        if stats['active_notebook']:
            print(f"  Active: {stats['active_notebook']['name']}")
        if stats['most_used_notebook']:
            print(f"  Most used: {stats['most_used_notebook']['name']} ({stats['most_used_notebook']['use_count']} uses)")
        print(f"  Library path: {stats['library_path']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()