#!/usr/bin/env python3
"""Render an explicitly edited, silent rough cut of captured synthetic UI states."""
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
MEDIA=ROOT/'docs/portfolio/media'
SHOTS=[
 ('01-intro','For referral reviewers: check the supplied documents,\ninspect the evidence, and prepare a human-reviewed handoff.'),
 ('02-evidence','These synthetic documents contain different dates of birth.\nBoth source quotes remain visible; the system does not choose an identity.'),
 ('03-decision','The reviewer keeps the identity issue unresolved and records a reason.\nHuman corrections stay separate from original source facts.'),
 ('04-handoff','After both items are handled, create a confirmed local snapshot.\nThe unresolved identity warning remains prominent.'),
 ('06-stale','In the missing-report case, load a prepared source revision.\nThe earlier result becomes read-only; no model is called.'),
 ('07-prepared','Load the prepared result for the added synthetic report.\nThe new result has no attachment finding and does not inherit old decisions.'),
 ('05-export','Export the reviewed version-2 handoff with source references.\nThis is an actual local text export, not a server or clinical approval.'),
 ('08-evaluation','Offline baseline, Fake and replay counts expose failures and limitations.\nReal-model evaluation, operator review and final release are still pending.'),
]

def stamp(seconds): return f'00:{seconds//60:02}:{seconds%60:02},000'
def main():
    for name,_ in SHOTS:
        if not (MEDIA/(name+'.png')).exists(): raise SystemExit('Capture the actual UI frames first')
    audit=json.loads((MEDIA/'capture-audit.json').read_text())
    if len(audit['shots'])!=8 or audit['model_calls']!=0: raise SystemExit('Capture audit mismatch')
    srt='\n'.join(f'{i+1}\n{stamp(i*10)} --> {stamp((i+1)*10)}\n{text}\n' for i,(_,text) in enumerate(SHOTS))
    (MEDIA/'referral-demo-en.srt').write_text(srt)
    concat='ffconcat version 1.0\n'+''.join(f"file '{name}.png'\nduration 10\n" for name,_ in SHOTS)+f"file '{SHOTS[-1][0]}.png'\n"
    (MEDIA/'shots.ffconcat').write_text(concat)
    filters=("scale=1280:720,drawbox=x=0:y=0:w=1280:h=28:color=0x18323d:t=fill,"
        "drawtext=text='OFFLINE SYNTHETIC DEMO  |  EDITED ROUGH CUT  |  NO AI CALLS':fontcolor=white:fontsize=16:x=20:y=5,"
        "drawbox=x=0:y=620:w=1280:h=100:color=0x18323d:t=fill,"
        "subtitles=referral-demo-en.srt:force_style='Fontname=Arial,Fontsize=11,PrimaryColour=&H00FFFFFF,Outline=0,Shadow=0,Alignment=2,MarginV=10'")
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i','shots.ffconcat',
        '-vf',filters,'-t','80','-r','15','-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart','referral-demo-rough-cut.mp4'],cwd=MEDIA,check=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json','referral-demo-rough-cut.mp4'],cwd=MEDIA))
    video=next(s for s in probe['streams'] if s['codec_type']=='video')
    assert 60<=float(probe['format']['duration'])<=90
    result=dict(duration_seconds=float(probe['format']['duration']),width=video['width'],height=video['height'],codec=video['codec_name'],
        frame_count=int(video['nb_frames']),caption_cues=len(SHOTS),captions='burned-in English; sidecar SRT',audio='none; silent rough cut',
        source='Actual offline UI states; still-frame holds and edits, not a continuous screen recording',bytes=int(probe['format']['size']))
    (MEDIA/'media-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
