import os
import sys
import logging
from git import Repo
import git


def update():
    # Path to your local repository
    repo_path = 'C:\\Users\Adam\Programming\Python\derpr-python'
    # 'https://github.com/Addrick/derpr-python/tree/master'

    # Open the repository
    repo = Repo(repo_path)

    # Pull the latest changes from the remote repository
    origin = repo.remotes.origin
    result = origin.pull()

    if (result[0].flags & 4) != 0:
        print("Pull successful. Changed files:")
        # Get the changes after the pull
        # changes = repo.git.diff('HEAD@{1}', 'HEAD')
        diff_index = repo.index.diff(None)
        for diff_added in diff_index.iter_change_type('A'):
            print(f"Added: {diff_added.b_path}")
        for diff_modified in diff_index.iter_change_type('M'):
            print(f"Modified: {diff_modified.b_path}")
        for diff_deleted in diff_index.iter_change_type('D'):
            print(f"Deleted: {diff_deleted.b_path}")

    else:
        print("Pull failed.")


def restart():
    # Restart the Python program
    logging.info('Restarting application...')
    print('Restarting application...')
    os.execv(sys.executable, [sys.executable] + sys.argv)


# update()
restart()

