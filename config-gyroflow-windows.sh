# SPDX-License-Identifier: GPL-3.0-or-later
# Preserve the codec selection of the deployed Windows 8.1 SDK.
. ./config-gpl-lite.sh
DEC_OPT="--enable-decoder=*sub*,movtext,*web*,aac*,ac3*,eac3*,alac*,ape,ass,av1*,ccaption,cfhd,cook,dca,dnxhd,exr,truehd,*yuv*,flv,flac,gif,h26[3-4]*,hevc*,hap,mp[1-3]*,prores*,*[mj]peg*,mlp,mpl2,nellymoser,opus,pcm*,qtrle,*png*,tiff,rawvideo,sami,srt,ssa,v210*,vc1*,vorbis,vp[6-9]*,wm*,wrapped_avframe,rv*,ffv*"
ENC_OPT="--enable-encoder=libx26*,aac,cfhd,dnxhd,exr,ff*,flv,*yuv*,gif,h26[3-4]*,av1*,hevc*,mjpeg*,*png,opus,pcm*,prores*,rawvideo,spdif,speedhq,*jpeg,*png,tiff,vp[8-9]*,wrapped_avframe,*nvenc,*qsv,*v4l2m2m,*vaapi,vorbis"
DEMUX_OPT="--enable-demuxer=*sub*,*ac3,*ac,*avs*,*[mj]peg*,*vc*,*web*,au,ape,ass,av[1i],concat,dnxhd,dts*,*dash*,*flv,gif,hls,h264,kux,matroska,mov,mp3,mxf,obu,ogg,pcm*,rawvideo,rt*p,spdif,srt,v210*,wav,*pipe,image2,mlv,nsv,nut"
MUX_OPT="--enable-muxer=*jpeg,dnxhd,fifo,flv,gif,hls,h264,hevc,image2,mov,mp4,mpegts,matroska,null,og*,pcm*,rawvideo,rt*,spdif,*pipe,*segment,webm,wav,dash,nu*"
PROT_OPT="--enable-protocol=cache,concat*,crypto*,data,fd,*file,ftp,h*,i*,pipe,rt*,s*,t*,u*"
FILTER_OPT="--enable-filter=drawtext,*null*,afade,*fifo,*format,*resample,aeval,atempo,pan,crop,eq*,framerate,hw*,loudnorm,scale,volume,yadif*,*movie,overlay,allrgb,allyuv,*bars,color,test*,*key,draw*,*_qsv,*_vaapi,*v4l2*"
USER_OPT="$USER_OPT --disable-filter=scale_cuda"
MUX_OPT="$MUX_OPT --enable-muxer=framecrc,framehash"
