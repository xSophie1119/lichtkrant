"""Track actual local audio process completion, separately from duration estimates."""
import secrets
import threading
import time
from collections import OrderedDict


class PlaybackTracker:
    def __init__(self):
        self.lock = threading.RLock()
        self.jobs = OrderedDict()

    def add(self, process):
        with self.lock:
            token = secrets.token_hex(16)
            self.jobs[token] = {'process': process, 'started': time.monotonic(), 'cancelled': False}
            while len(self.jobs) > 40: self.jobs.popitem(last=False)
            return token

    def cancel(self, process):
        with self.lock:
            for job in self.jobs.values():
                if job['process'] is process: job['cancelled'] = True

    def status(self, token):
        with self.lock:
            job = self.jobs.get(token)
            if not job: return {'ok': False, 'status': 'error', 'error': 'Afspeelopdracht niet gevonden'}
            code = job['process'].poll()
            if job['cancelled']: return {'ok': True, 'status': 'cancelled', 'detail': 'Omroep gestopt'}
            if code is None: return {'ok': True, 'status': 'playing'}
            if code != 0: return {'ok': False, 'status': 'error', 'error': f'Audiospeler gestopt met foutcode {code}'}
            return {'ok': True, 'status': 'completed', 'detail': 'Audiospeler heeft de omroep afgerond'}


def attenuate_wav(audio, volume):
    """SoundPlayer has no volume knob: scale PCM samples without touching OS gain."""
    import array
    import io
    import sys
    import wave
    gain = max(0, min(100, int(volume))) / 100
    if gain == 1: return audio
    with wave.open(io.BytesIO(audio), 'rb') as source:
        params = source.getparams()
        data = source.readframes(source.getnframes())
    width = params.sampwidth
    if width == 2:
        samples = array.array('h'); samples.frombytes(data)
        if sys.byteorder != 'little': samples.byteswap()
        samples = array.array('h', (round(value * gain) for value in samples))
        if sys.byteorder != 'little': samples.byteswap()
        data = samples.tobytes()
    elif width == 1:
        data = bytes(round((value-128)*gain)+128 for value in data)
    elif width in {3, 4}:
        data = b''.join(round(int.from_bytes(data[i:i+width], 'little', signed=True)*gain).to_bytes(width, 'little', signed=True) for i in range(0, len(data), width))
    else:
        raise ValueError('Niet-ondersteund PCM-formaat voor volumeregeling')
    result = io.BytesIO()
    with wave.open(result, 'wb') as target:
        target.setparams(params); target.writeframes(data)
    return result.getvalue()
