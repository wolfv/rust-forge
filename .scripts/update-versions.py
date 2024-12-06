import os
import sys
import yaml
import requests
from pathlib import Path
import hashlib

def get_github_latest_release(repo: str, package_name: str):
    """Get latest release version from GitHub."""
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"

    # Use GitHub token if available
    token = os.getenv('GITHUB_TOKEN')
    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'

    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        tag_name = response.json()['tag_name']

        if tag_name.startswith(package_name):
            tag_name = tag_name[len(package_name)+1:]
        if tag_name.startswith('v'):
            tag_name = tag_name[1:]
    
        return tag_name
    return None

def calculate_sha256(url):
    """Download file and calculate SHA256."""
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        sha256_hash = hashlib.sha256()
        for chunk in response.iter_content(chunk_size=8192):
            sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    return None

def replace_version_string(content, new_version):
    """Replace first occurrence of version in content, line by line."""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith('version:'):
            # Keep the leading whitespace
            whitespace = line[:line.index('version:')]
            lines[i] = f'{whitespace}version: "{new_version}"'
            break
    return '\n'.join(lines)

def update_recipe(recipe_path):
    """Update version and hash in recipe file."""
    with open(recipe_path) as f:
        recipe = yaml.safe_load(f)

    current_version = recipe['context']['version']
    source_url = recipe['source']['url']
    old_hash = recipe['source']['sha256']
    package_name = recipe['package']['name']

    # Determine package source (GitHub or PyPI)
    if 'github.com' in source_url:
        # Extract owner/repo from GitHub URL
        repo = '/'.join(source_url.split('github.com/')[1].split('/')[0:2])
        new_version = get_github_latest_release(repo, package_name)
    else:
        print(f"Unsupported source URL format: {source_url}")
        return

    if not new_version:
        print(f"Could not fetch new version for {recipe_path}")
        return

    if new_version == current_version:
        print(f"Already at latest version: {current_version}")
        return

    print(f"Checking package {recipe['package']['name']} for updates")
    print(f"Current version: {current_version}, Latest version: {new_version}")
    # Update URL and calculate new hash
    new_url = source_url.replace("${{ version }}", new_version)
    new_hash = calculate_sha256(new_url)

    if not new_hash:
        print(f"Failed to calculate new hash for {recipe_path}")
        return

    # Update recipe as a string replace because we want to keep all YAML formatting
    recipe_str = recipe_path.read_text()
    recipe_str = replace_version_string(recipe_str, new_version)
    recipe_str = recipe_str.replace(old_hash, new_hash)

    # Save updated recipe
    recipe_path.write_text(recipe_str.strip())

    print(f"Updated {recipe_path}: {current_version} -> {new_version}")

def main():
    recipe_dir = Path('.')

    # take first arg from cli and use as recipe_dir
    if len(sys.argv) > 1:
        recipe_dir = Path(sys.argv[1])

    for recipe_file in recipe_dir.glob('**/recipe.yaml'):
        try:
            update_recipe(recipe_file)
        except Exception as e:
            print(f"Error processing {recipe_file}: {e}")

if __name__ == '__main__':
    main()
