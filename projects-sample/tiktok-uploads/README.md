# tiktok-uploads sample project

Copy this folder to wherever you want your TikTok project to live, then:

1. `cp upload-defaults.yaml.example upload-defaults.yaml` and edit
2. *(optional, for API mode)* `cp tiktok-api-creds.yaml.example tiktok-api-creds.yaml`, fill in OAuth tokens, `chmod 600`
3. Drop `.mp4` files into `videos/`
4. `~/.claude/skills/tiktok-upload/scripts/upload-queue.sh <this-dir>`

Browser mode is default; auto fallback if API creds missing.
