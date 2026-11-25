# VSL voice: energy-controllable clone (knowledge#18736)

**Why:** the bodies were made with Chatterbox **turbo**, which ignores `exaggeration` and `cfg_weight`, so "energetic" was never applied; the plane VSL used the old `tyler-ref.wav`.

## Candidates (license/capability from each project's published docs; NOT yet measured on our hardware)
| model | license | energy / emotion control | notes |
|---|---|---|---|
| Chatterbox (non-turbo) | MIT | `exaggeration`, `cfg_weight` honoured | same family we already run; lowest-risk swap |
| CosyVoice 2/3 | Apache-2.0 | instruct text ("speak with high energy") | zero-shot clone + natural-language style |
| IndexTTS2 | Index-TTS license (check commercial terms) | explicit emotion vector / `emo_alpha` | strongest emotion control; licence needs a read before a pick |
| Orpheus | Apache-2.0 | emotion tags | cloning needs a finetune, weakest clone fidelity for a one-reference voice |
| F5-TTS, Fish/OpenAudio | CC-BY-NC weights | style follows the reference only | dropped: non-commercial weights and no energy knob |
Do-nothing (turbo) is the defect. All candidates are local, flat-cost.

## Run (user `vsl` on novaserver; needs the model installs, a clean Tyler reference wav, a GPU or patience)
```
python3 voice/blind_test.py --script rows.txt --ref <tyler-ref.wav> --models chatterbox,cosyvoice,indextts2
```
`rows.txt` = `build_intro.py <pkg> <tag> --rows-only` output for 3307. Writes `samples/<model>.wav` (-16 LUFS, measured by ebur128) + `<model>.json` (model, license, render time, LUFS, reference sha256) and `samples/blind-key.json` (A/B/C -> model, kept apart). A model that cannot load is reported and skipped, never faked; exit 2 if fewer than 3 render.

## After Tyler's pick
Set `profile.yaml` (`picked: true`, id, model, reference, `reference_sha256`). `render/build_intro.py` stamps `voice_profile` + `voice_reference_sha256` into every sidecar; VERIFY runs `python3 voice/voice_profile.py check <tag>-intro.json` and fails on a wrong id or a changed reference.
