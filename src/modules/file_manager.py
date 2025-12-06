import os
import re
import shutil

class FileManager:
    """
    A utility class to handle all filesystem operations.
    This separates the logic of *where* and *how* we save files from the main app logic.
    """
    def __init__(self, base_path="Output_Folder"):
        # The default bucket where all user data will be saved.
        self.base_path = base_path
        # Create the base directory immediately if it doesn't exist.
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)

    def sanitize_filename(self, filename):
        """
        Cleans a string so it can be safely used as a filename.
        Operating systems (especially Windows) forbid characters like < > : " / \ | ? *
        """
        # Regex substitution: Replace any matched invalid char with an empty string.
        return re.sub(r'[\\/*?:"<>|]', "", filename).strip()

    def create_project_folder(self, folder_name):
        """
        Creates a dedicated folder for the current search query (e.g., "[2017] Attention Is All You Need").
        Returns the absolute path to this new folder.
        """
        safe_name = self.sanitize_filename(folder_name)
        # Combine base path and safe name into a full directory path
        path = os.path.join(self.base_path, safe_name)
        
        # Only create if it doesn't already exist
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def save_text(self, content, directory, filename):
        """
        Saves raw text to a file. Used for saving Abstracts when the PDF isn't available.
        Using 'utf-8' encoding is crucial for handling scientific characters or foreign languages.
        """
        path = os.path.join(directory, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def zip_directory(self, folder_path):
        """
        Compresses a folder into a ZIP file.
        Useful for bundling the results for easy download or sharing.
        (Note: Unused in the final UI version as the user prefers persistent folders, but kept for utility).
        """
        zip_path = f"{folder_path}.zip"
        # shutil is a high-level file operations library in Python.
        shutil.make_archive(folder_path, 'zip', folder_path)
        return zip_path
