# Your folder, code editor, Codex, and GitHub

## One local folder, several tools

On the creator's current Mac the actual repository is:

`/Users/hamzah_ali/Documents/Codex/2026-10-02/i-will-be-brain-dumping-my/outputs/storyroom`

For another contributor, use the root of their clone instead. This original chat
started above the repository. Prefer this inner folder as the primary folder for
new local Codex work; do not initialize or stage the parent home repository.

| Place | What it does | What it does not do |
| --- | --- | --- |
| Local repository folder | Stores source files, documentation, and local Git history | Does not automatically upload changes |
| VS Code | Lets you read/edit those same files and inspect diffs | Does not need a separate copy of the project |
| Codex local project | Gives coding sessions access to the selected folder | A new chat should not be assumed to remember this entire conversation |
| Running Storyroom | Executes frontend, API, and worker against local data | Opening a source file or GitHub page does not start it |
| GitHub repository | Stores pushed commits for remote viewing/collaboration | Is not the running application, footage backup, or chat sync |

Open this folder with VS Code's File → Open Folder. In the desktop app, attach
it as the local project's primary folder. New chats start in that primary folder;
it is also used for Git operations and project-instruction discovery. See
[official project documentation](https://learn.chatgpt.com/docs/projects).

`AGENTS.md` is specifically for agent instructions. The other Markdown files are
ordinary project documentation, not magic memory. AGENTS points to the handoff
and context so future sessions know what to read. See
[official AGENTS guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Everyday loop

1. Open the same repo in VS Code and the local coding session. Use HANDOFF for a
   new chat and STATUS to choose one observable improvement.
2. Work on a focused branch (normally `codex/<topic>`). Avoid two sessions editing
   the same files at once. Save your own editor changes before asking an agent to
   change those files; review what changed before saving an older editor buffer.
3. Start the app using README. Keep the launch terminal alive while using localhost.
   The URL works on that machine while its servers run; GitHub does not host it.
4. Inspect the diff, run appropriate checks, and try the behavior. Ask the agent to
   explain the input, output, state, and failure paths. Update the relevant docs.
5. Commit a coherent checkpoint locally. Push the branch when you want those
   commits on GitHub. Review/merge via a pull request when useful.

For this project, the creator requested on 2026-10-09 that verified implementation
checkpoints be pushed routinely with descriptive commit messages and updates.
The connected remote [Humza1423/storyroom](https://github.com/Humza1423/storyroom)
is public (verified through GitHub that day). Agents should push the feature branch,
open/update its pull request, check CI and provide direct links. Merging to main and
changing visibility are separate decisions. On GitHub, select the feature branch
or follow the provided PR link to see its updated README before merge.

Git vocabulary: **save** updates a file; **commit** records a local snapshot;
**push** sends commits to the configured remote; **pull** brings remote changes
into the local branch. Inspect local changes before pulling. Git is not automatic
two-way synchronization, and uncommitted edits do not appear on GitHub.

Use `git status --short --branch` to see local changes and `git remote -v` to see
the remote destination. Check the selected branch on GitHub if a pushed change
doesn't appear. Review files before staging; never use the parent directory here.

## Another computer or a cloud coding environment

Clone the remote repository after it exists and follow README for dependencies.
You receive pushed source/docs, not the local `.env`, database, clips, or exports.
Configure credentials locally; never paste them into a handoff or chat. Synthetic
fixtures can be regenerated. Personal projects require a separate secure backup
of the complete `data/` directory with the app stopped.

Resolve exports reference normalized media on the originating machine. Copying
source code alone does not make those exports portable. Cross-device media
packaging/relinking is future work. Connecting GitHub also does not itself move
this conversation to another app or make a localhost URL reachable on a phone.
