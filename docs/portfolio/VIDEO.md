# 80-second captioned walkthrough — MVP review

File: [referral-demo-rough-cut.mp4](media/referral-demo-rough-cut.mp4) (historical filename retained). Public sharing target: [walkthrough.mp4](https://meditrace-portfolio-mvp.vercel.app/walkthrough.mp4). English captions are burned in; [SRT](media/referral-demo-en.srt) is provided separately. Silent H.264 MP4, 1280×720. This is an **edited still-frame walkthrough** of actual synthetic UI interactions, with deliberate reading holds. It is not a continuous live recording, a narrated film, or real model execution.

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
| 01:10–01:20 | Evaluation page with offline counts and unmeasured real-model quality | Show measurement limits |

The six workflow frames from 2026-10-22 were compared with the current shared components and verified demo flow and retained. The intro and evaluation frames were refreshed from the public MVP on 2026-10-27 to reflect the current navigation and wording; see [refresh audit](media/refresh-audit.json). The [original capture audit](media/capture-audit.json) remains historical evidence, not a claim that all frames were captured again.

[confirmed-demo.txt](media/confirmed-demo.txt) is the original identity-case Blob text exported during capture; [prepared-demo.txt](media/prepared-demo.txt) is the revision-2 export. No private browser windows, accounts, patient records or credentials were captured. No model was called or local application service started.

## Reproduce

1. Keep the six original workflow PNGs. The original offline harness/capture scripts remain available for a full recapture if that workflow changes.
2. With a dedicated headless Chrome on port 9468, run `node scripts/portfolio_browser_qa.cjs artifacts/portfolio/build-EXAMPLE/site 9468 --live --refresh-video`. This checks the public synthetic flow and refreshes only the intro/evaluation frames. Do not reuse another task's session or foreground a window.
3. `python3 scripts/referral_portfolio_video.py` renders the video, decodes the entire MP4, extracts an eight-shot contact sheet and writes `media-check.json` with duration, dimensions, frame count and SHA-256.
4. Inspect [the contact sheet](media/contact-sheet.png), then build/release the static portfolio. The build includes the reviewed video at `/walkthrough.mp4`; browser acceptance checks the video response, byte count and advertised H.264 support.

Only this task's dedicated browser should be closed afterward. The initial default DevTools profile was already owned by another session and was left untouched.

## MVP review boundaries

The revised captions and banner explicitly label synthetic data, edited still frames and no AI calls. The final caption no longer describes the portfolio release as pending; real-model and clinical measurements remain unmeasured. There is no narration or first-person contribution claim. The video is sufficient for the scoped portfolio MVP and does not close the full V1 MT-23 ticket. Full-file playback decoding and public download verification are recorded in [the release notes](STATIC-DEMO.md).

The background Chrome harness deferred media playback, so it does not establish interactive browser playback. The complete H.264 file passed FFmpeg decoding; the public bytes and browser codec support are checked separately. No browser window was foregrounded for this check.
