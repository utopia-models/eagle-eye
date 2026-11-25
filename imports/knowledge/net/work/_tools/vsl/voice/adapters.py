"""Per-model TTS adapters for the voice blind test (knowledge#18736). Each is lazy: importing this file needs no model.
synth(text, ref_wav, energy) -> (mono float32 ndarray, sample_rate). Missing package or weights -> AdapterUnavailable,
never a silent fallback (a fake sample would put a wrong voice in Tyler's ear)."""
import os


class AdapterUnavailable(RuntimeError):
    pass


def _need(mod):
    try:
        return __import__(mod, fromlist=["_"])
    except Exception as e:  # ImportError or a broken native dep
        raise AdapterUnavailable(f"python package {mod!r} not importable: {e}")


class Chatterbox:
    name, license = "chatterbox", "MIT"   # NON-turbo ChatterboxTTS: exaggeration + cfg_weight are honoured (turbo ignores both)
    def __init__(self):
        self.m = _need("chatterbox.tts").ChatterboxTTS.from_pretrained(device=os.environ.get("VOICE_DEVICE", "cpu"))
    def synth(self, text, ref, energy):
        w = self.m.generate(text, audio_prompt_path=ref, exaggeration=0.25 + 0.9 * energy, cfg_weight=0.5 - 0.3 * energy)
        return w.squeeze().cpu().numpy().astype("float32"), self.m.sr


class CosyVoice:
    name, license = "cosyvoice", "Apache-2.0"   # CosyVoice 2/3 zero-shot + instruct text ("speak with high energy")
    def __init__(self):
        d = os.environ.get("COSYVOICE_MODEL_DIR")
        if not d or not os.path.isdir(d):
            raise AdapterUnavailable("COSYVOICE_MODEL_DIR is not set to a downloaded CosyVoice2 model dir")
        self.m = _need("cosyvoice.cli.cosyvoice").CosyVoice2(d)
    def synth(self, text, ref, energy):
        import numpy as np
        load = _need("cosyvoice.utils.file_utils").load_wav
        inst = "Speak with high energy and enthusiasm." if energy >= 0.6 else "Speak in a calm, even tone."
        chunks = [o["tts_speech"].squeeze().numpy() for o in self.m.inference_instruct2(text, inst, load(ref, 16000), stream=False)]
        return np.concatenate(chunks).astype("float32"), self.m.sample_rate


class IndexTTS2:
    name, license = "indextts2", "Index-TTS license (check commercial terms before pick)"   # explicit emotion control: emo_alpha
    def __init__(self):
        d = os.environ.get("INDEXTTS2_DIR")
        if not d or not os.path.isdir(d):
            raise AdapterUnavailable("INDEXTTS2_DIR is not set to a checkpoint dir with config.yaml")
        self.m = _need("indextts.infer_v2").IndexTTS2(cfg_path=os.path.join(d, "config.yaml"), model_dir=d)
    def synth(self, text, ref, energy):
        import soundfile as sf, tempfile
        out = tempfile.mktemp(suffix=".wav")
        self.m.infer(spk_audio_prompt=ref, text=text, output_path=out, emo_alpha=0.3 + 0.7 * energy, use_emo_text=True)
        a, sr = sf.read(out); os.unlink(out)
        return a.astype("float32"), sr


class Orpheus:
    name, license = "orpheus", "Apache-2.0"   # emotion tags (<laugh>, <sigh>); cloning needs the community finetune, reference via prompt
    def __init__(self):
        self.m = _need("orpheus_tts").OrpheusModel(model_name=os.environ.get("ORPHEUS_MODEL", "canopylabs/orpheus-3b-0.1-ft"))
    def synth(self, text, ref, energy):
        import numpy as np
        pcm = b"".join(self.m.generate_speech(prompt=text, voice=os.environ.get("ORPHEUS_VOICE", "tara")))
        return np.frombuffer(pcm, dtype="int16").astype("float32") / 32768.0, 24000


ADAPTERS = {c.name: c for c in (Chatterbox, CosyVoice, IndexTTS2, Orpheus)}
