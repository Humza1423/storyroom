# Third-party and media notes

Application code is MIT. Installed packages retain their own licenses. Dependency declarations and npm's lockfile identify what was installed; do not imply MIT covers every dependency, model weight, or video.

- React, FastAPI, Vite, dnd-kit, and OpenTimelineIO are separate upstream projects. Review their distributed license notices when packaging.
- FFmpeg licensing depends on the build and enabled codecs. This application invokes a separately installed FFmpeg executable; it does not bundle FFmpeg binaries.
- Gemini inference is a hosted service governed by its provider terms. Keys and paid accounts belong to each user. The open-source app is not a free Gemini service.
- SigLIP, DINO, SAM, YOLO, InternVideo, and Florence are discussed as potential experiments only. Their weights are not included. Verify each exact checkpoint's license before integration.
- The sample project is generated locally from FFmpeg test patterns and tones. It depicts no real athlete, contains no third-party stock clip, and must not be represented as a real-world AI benchmark.

## Real-footage provenance

Every imported asset has fields for source, author, license/permission, cloud analysis, model training, and redistribution. These fields record the user's review; they do not automatically establish permission. Use per-file source evidence rather than a site's general “free” label. Do not publish user footage in the repository.

No third-party real-footage dataset has yet been vetted or bundled. Technical fixture tests can run now; training and human retrieval evaluation remain pending.
