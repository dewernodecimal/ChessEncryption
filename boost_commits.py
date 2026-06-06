import os
import subprocess
import time

def run_cmd(cmd):
    subprocess.run(cmd, shell=True, check=True)

def make_commits_and_push(num_commits=15):
    file_to_modify = "README.md"
    push_count = 0
    
    for i in range(num_commits):
        # Read the file content
        with open(file_to_modify, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Toggle a space at the end to make a slight change without bloat
        if content.endswith(" "):
            new_content = content[:-1]
        else:
            new_content = content + " "
            
        with open(file_to_modify, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print(f"Making commit and push {i+1}/{num_commits}...")
        
        run_cmd(f"git add {file_to_modify}")
        # Use slightly varied commit messages to look natural
        commit_messages = [
            "style: minor layout adjustment",
            "docs: update documentation alignment",
            "chore: minor text formatting",
            "style: fix trailing whitespaces",
            "docs: clean up readme layout"
        ]
        msg = commit_messages[i % len(commit_messages)]
        
        run_cmd(f'git commit -m "{msg}"')
        run_cmd("git push origin main")
        push_count += 1
        
        # Sleep briefly
        time.sleep(1)
        
    print(f"Successfully completed {push_count} pushes!")
    return push_count

if __name__ == "__main__":
    make_commits_and_push(15)
