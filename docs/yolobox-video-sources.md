# YoloBox video sources

NightAzimuth supports a YoloBox as a local UVC video source without requiring NightAzimuth to control the HDMI camera directly.

## Recommended path

`DSLR / mirrorless camera → HDMI → YoloBox → USB/UVC → NightAzimuth browser`

In Settings → Camera identification → Video source, choose **YoloBox UVC**, then choose **Detect video sources**. NightAzimuth prefers video devices whose browser label identifies YoloBox/YoloLiv and stores that device selection locally.

Because UVC is exposed to the browser as a normal camera device, the existing NightAzimuth preview, test-frame capture, bright-point detection and plate-solving workflow remains unchanged.

## Direct camera / capture device

Choose **Direct camera / webcam** for a normal webcam, directly connected camera, or generic HDMI capture device.

## Network stream bridge

NightAzimuth records RTSP, SRT, RTMP, NDI or other upstream transport metadata plus an HTTPS browser-bridge URL. These protocols are not consumed directly by the hosted browser application. The hosted Content Security Policy is not weakened to allow arbitrary external media.

For live preview, capture and plate solving, use YoloBox UVC. A future/local gateway can consume the stored network bridge configuration and expose a browser-safe stream without changing the camera source model.

No credentials or stream secrets should be stored in the public frontend configuration.
