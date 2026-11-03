"""Experimental native joint-H3 latent mask, not an output audio edit."""
import math

def audio_window_indices(steps,duration,start,end):
    if type(steps) is not int or steps<1 or any(type(v) not in (int,float) or not math.isfinite(v) for v in [duration,start,end]):
        raise ValueError('Use finite audio-window seconds and an integer step count.')
    if not 0<=start<end<=duration:raise ValueError('Speech window must fit the sampled timeline.')
    first=math.ceil(start*steps/duration-1e-9);last=math.floor(end*steps/duration+1e-9)
    if first>=last:raise ValueError('Speech window contains no complete audio latent step.')
    return first,last

def mask_h3_audio(av_latent,audio_vae,window):
    import torch
    import torch.nn.functional as F
    import comfy.nested_tensor
    if av_latent.get('noise_mask') is not None:raise ValueError('This experimental adapter accepts an unmasked native H3 AV latent only.')
    samples=av_latent.get('samples')
    if not getattr(samples,'is_nested',False):raise ValueError('Expected native joint H3 AV latent, not a context cache or generic latent.')
    parts=samples.unbind()
    if len(parts)!=2:raise ValueError('Expected exactly video and audio latent streams.')
    video,audio=parts
    if abs(audio.shape[-1]-window['sampling_end_s']*40)>.50001:
        raise ValueError('Native H3 audio latent timeline does not match the declared sampling duration at40Hz.')
    first,last=audio_window_indices(audio.shape[-1],window['sampling_end_s'],window['speech_start_s'],window['speech_end_s'])
    sample_rate=int(getattr(audio_vae,'audio_sample_rate',32000))
    waveform=torch.zeros((audio.shape[0],2,round(window['sampling_end_s']*sample_rate)),device='cpu')
    silence=audio_vae.encode(waveform.movedim(1,-1))
    if silence.shape[:-1]!=audio.shape[:-1]:raise ValueError('Audio VAE does not match this native H3 audio latent.')
    silence=F.pad(silence,(0,max(0,audio.shape[-1]-silence.shape[-1])))[...,:audio.shape[-1]].to(audio)
    masked_audio=audio.clone();masked_audio[...,:first]=silence[...,:first];masked_audio[...,last:]=silence[...,last:]
    audio_mask=torch.zeros_like(audio);audio_mask[...,first:last]=1
    result=dict(av_latent)
    result['samples']=comfy.nested_tensor.NestedTensor((video,masked_audio))
    result['noise_mask']=comfy.nested_tensor.NestedTensor((torch.ones_like(video),audio_mask))
    return result
