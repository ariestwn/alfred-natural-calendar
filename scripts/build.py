#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build.py - Build script for Alfred Natural Calendar Workflow
Creates a distributable .alfredworkflow file including all necessary assets
"""

import os
import sys
import shutil
import subprocess
import zipfile
import tempfile
from datetime import datetime

class WorkflowBuilder:
    def __init__(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        self.workflow_dir = os.path.join(self.root_dir, 'workflow')
        self.dist_dir = os.path.join(self.root_dir, 'dist')
        self.version = self.get_version()

    def get_version(self):
        """Get version from info.plist or git tag"""
        try:
            result = subprocess.run(
                ['git', 'describe', '--tags', '--always'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except:
            return datetime.now().strftime('%Y%m%d')

    def create_workflow_bundle(self):
        """Create Alfred workflow bundle"""
        print("\nCreating workflow bundle...")
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy all workflow files (except lib and local bytecode caches)
            for item in os.listdir(self.workflow_dir):
                if item not in ('lib', '__pycache__'):
                    src = os.path.join(self.workflow_dir, item)
                    dst = os.path.join(temp_dir, item)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)
                    elif os.path.isdir(src):
                        shutil.copytree(src, dst)

            # Create output directory if it doesn't exist
            os.makedirs(self.dist_dir, exist_ok=True)

            # Create workflow bundle
            output_file = os.path.join(
                self.dist_dir,
                f'Natural-Calendar-{self.version}.alfredworkflow'
            )

            # Remove existing file if it exists
            if os.path.exists(output_file):
                os.remove(output_file)

            # Create workflow bundle
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)

            print(f"✓ Workflow bundle created: {output_file}")
            return output_file

    def verify_files(self):
        """Verify all required files exist"""
        required_files = [
            'calendar_nlp.py',
            'preview.py',
            'calendar_profile.py',
            'date_parser.py',
            'info.plist',
            'icon.png',
            'setup.py'
        ]
        
        missing_files = []
        for file in required_files:
            if not os.path.exists(os.path.join(self.workflow_dir, file)):
                missing_files.append(file)
        
        if missing_files:
            print("❌ Missing required files:")
            for file in missing_files:
                print(f"  - {file}")
            return False
        return True

    def build(self):
        """Run complete build process"""
        print(f"Building Natural Calendar Workflow v{self.version}")
        
        try:
            # Verify all required files exist
            if not self.verify_files():
                sys.exit(1)

            # Create the workflow bundle
            output_file = self.create_workflow_bundle()
            
            print("\n✅ Build completed successfully!")
            print(f"Workflow package: {output_file}")
            
        except Exception as e:
            print(f"\n❌ Error during build: {str(e)}")
            sys.exit(1)

def main():
    builder = WorkflowBuilder()
    builder.build()

if __name__ == '__main__':
    main()
