import { Composition } from "remotion";
import { Promo } from "./Promo";
import { DURATION, FPS, HEIGHT, WIDTH } from "./theme";

export function RemotionRoot() {
  return (
    <Composition id="Promo" component={Promo} durationInFrames={DURATION} fps={FPS} width={WIDTH} height={HEIGHT} />
  );
}
