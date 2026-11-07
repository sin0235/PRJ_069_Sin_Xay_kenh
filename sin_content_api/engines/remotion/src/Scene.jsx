import React, {useEffect, useRef, useState} from 'react';
import {delayRender, continueRender, useCurrentFrame, useVideoConfig} from 'remotion';

// Trang cảnh giấy là hàm thuần của t: ở mỗi khung chỉ cần gọi window.setT(t) trong iframe rồi để Remotion chụp.
export const Scene = ({html}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const frameRef = useRef(null);
  const [loadHandle] = useState(() => delayRender('Nạp trang cảnh'));
  const [ready, setReady] = useState(false);
  const loaded = useRef(false);

  useEffect(() => {
    if (!ready) return undefined;
    const handle = delayRender(`Đặt t cho khung ${frame}`);
    const win = frameRef.current.contentWindow;
    let cancelled = false;
    Promise.resolve(win.document.fonts.load('700 54px Viet')).then(() => {
      if (cancelled) return;
      win.setT(frame / fps);
      // Chờ hai lần vẽ để SVG mới được dựng xong trước khi Remotion chụp.
      win.requestAnimationFrame(() => win.requestAnimationFrame(() => {
        continueRender(handle);
        if (!loaded.current) { loaded.current = true; continueRender(loadHandle); }
      }));
    });
    return () => { cancelled = true; };
  }, [frame, fps, ready, loadHandle]);

  return (
    <iframe
      ref={frameRef}
      title="canh"
      srcDoc={html}
      onLoad={() => setReady(true)}
      style={{width, height, border: 0, display: 'block'}}
    />
  );
};
