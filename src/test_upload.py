from src.upload_youtube import youtube_uploader
from src.upload_facebook import facebook_uploader

# Use the small test video
video_path = "src/test_assets/test_video.mp4"

# Dummy metadata
title = "Test Upload"
description = "This is a test upload video"
tags = ["test", "upload"]
publish_at_iso = "2026-03-14T12:00:00.000Z"  # some future time in UTC

# Upload to YouTube
yt_video_id = youtube_uploader.upload_video(video_path, title, description, tags, publish_at_iso)
print(f"YouTube video id: {yt_video_id}")

# Upload to Facebook
fb_video_id = facebook_uploader.upload_video(video_path, title, description, tags, publish_at_iso)
print(f"Facebook video id: {fb_video_id}")