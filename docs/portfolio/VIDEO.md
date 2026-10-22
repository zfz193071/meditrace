# 80-second captioned walkthrough — rough cut

File: [referral-demo-rough-cut.mp4](media/referral-demo-rough-cut.mp4). English captions are burned in; [SRT](media/referral-demo-en.srt) is provided separately. Silent H.264 MP4, 1280×720. This is an **edited still-frame walkthrough** of actual offline UI interactions, with deliberate reading holds. It is not a continuous live recording, a narrated final film, or real model execution.

## Shot list

| Time | Actual captured state | Caption purpose |
| --- | --- | --- |
| 00:00–00:10 | Demo entry, synthetic labels, case choices | Identify referral reviewers and the document-review task |
| 00:10–00:20 | Both highlighted DOB quotes | Show the discrepancy without choosing an identity |
| 00:20–00:30 | Keep unresolved with a reviewer-entered reason | Separate the human decision from source facts |
| 00:30–00:40 | Confirmed local handoff and identity warning | Show explicit confirmation, not clinical approval |
| 00:40–00:50 | Missing-report case, source revision 2 loaded, old result stale | Explain source-version invalidation |
| 00:50–01:00 | Prepared revision-2 result with no attachment finding | Clearly identify prepared material, not a new model response |
| 01:00–01:10 | Confirmed version-2 handoff after text download | Export the updated source context |
| 01:10–01:20 | Evaluation page with measured counts and blocker notice | Show limitations and unmeasured real-model quality |

All eight source frames and [capture audit](media/capture-audit.json) are retained. [confirmed-demo.txt](media/confirmed-demo.txt) is the identity-case Blob text actually exported during capture; [prepared-demo.txt](media/prepared-demo.txt) is the later revision-2 export. Private browser windows, accounts, patient records and credentials were not captured. The same current components as the workspace/demo were compiled into the offline harness; no Next/FastAPI service was started.

## Reproduce

1. `node scripts/referral_demo_qa.cjs` produces an offline harness path.
2. Start a dedicated **headless** Chrome with an isolated user-data directory and DevTools port 9456; do not reuse another task's session or foreground a window.
3. `node scripts/referral_portfolio_capture.cjs capture file:///.../index.html` operates only fixed synthetic results and captures the states. It refuses unexpected HTTP(S) requests.
4. `python3 scripts/referral_portfolio_video.py` renders the still-frame rough cut using installed FFmpeg/ffprobe and writes `media-check.json`.
5. Decode the complete MP4 to check corruption and inspect frames around caption transitions. The media report records the measured duration and stream properties.

Only this task's dedicated browser should be closed afterward. The initial default DevTools profile was already owned by another session and was left untouched.

## Before a final public version

The rough cut is a locally playable deliverable, not final MT-23 acceptance. After MT-16/20/22 acceptance, recheck all metrics and claims, replace affected shots, consider a continuous capture or narration, and verify playback and links on the intended public host. The user must approve personal attribution and any spoken first-person claims. Publishing, posting to Discord or deploying the site is not part of this draft task.
