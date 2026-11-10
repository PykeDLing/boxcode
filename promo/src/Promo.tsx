// 整部片子：七场，场与场之间淡入淡出；配乐从头铺到尾。

import type { ReactNode } from "react";
import { Html5Audio, staticFile } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { SCENES, TRANSITION } from "./theme";
import { End } from "./scenes/End";
import { Hook } from "./scenes/Hook";
import { Identity } from "./scenes/Identity";
import { Loop } from "./scenes/Loop";
import { Permission } from "./scenes/Permission";
import { Sandbox } from "./scenes/Sandbox";
import { Turn } from "./scenes/Turn";

const ORDER: [number, ReactNode][] = [
  [SCENES.hook, <Hook />],
  [SCENES.turn, <Turn />],
  [SCENES.identity, <Identity />],
  [SCENES.sandbox, <Sandbox />],
  [SCENES.loop, <Loop />],
  [SCENES.permission, <Permission />],
  [SCENES.end, <End />],
];

export function Promo() {
  return (
    <>
      {/* public/music.wav 由 music/compose.mjs 生成（npm run music） */}
      <Html5Audio src={staticFile("music.wav")} />
      <TransitionSeries>
      {ORDER.flatMap(([duration, scene], i) => {
        const parts = [
          <TransitionSeries.Sequence key={`scene-${i}`} durationInFrames={duration}>
            {scene}
          </TransitionSeries.Sequence>,
        ];
        if (i < ORDER.length - 1) {
          parts.push(
            <TransitionSeries.Transition
              key={`fade-${i}`}
              presentation={fade()}
              timing={linearTiming({ durationInFrames: TRANSITION })}
            />,
          );
        }
        return parts;
      })}
      </TransitionSeries>
    </>
  );
}
