import os
import sys
from git import Repo


def update():
    # Path to your local repository
    repo_path = 'C:\\Users\Adam\Programming\Python\derpr-python'
    # 'https://github.com/Addrick/derpr-python/tree/master'

    # Open the repository
    repo = Repo(repo_path)

    # Pull the latest changes from the remote repository
    origin = repo.remotes.origin
    result = origin.pull()
    print(result[0].flags)
    #
    # if pull_info is None:
    #     print("Pull successful. Changes:")
    #     # Get the changes after the pull
    #     changes = repo.git.diff('HEAD@{1}', 'HEAD')
    #     print(changes)
    # else:
    #     print("Pull failed. Error message:", pull_info)


def restart():
    # Restart the Python program
    os.execv(sys.executable, [sys.executable] + sys.argv)


update()
