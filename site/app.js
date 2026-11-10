// BoxCode 项目网页的两处交互：首屏的沙盒示意、代码块的复制按钮。
// 没有 JS 时页面照常可读：示意里的每一行本来就写在 HTML 里。

(function () {
  "use strict";

  // ---- 沙盒示意 ----
  const demo = document.getElementById("boxdemo");
  if (demo) {
    const box = demo.querySelector(".box");
    const rows = Array.from(demo.querySelectorAll("#demo-log li"));
    const targets = Array.from(demo.querySelectorAll(".outside li"));
    const toggle = document.getElementById("demo-toggle");
    const replay = document.getElementById("demo-replay");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const STEP_MS = 1500; // 每一行停留多久
    const END_MS = 4200; // 全部放完后停多久再重来
    let index = 0;
    let timer = null;
    let playing = false;

    function reset() {
      index = 0;
      rows.forEach((row) => row.classList.add("pending"));
      targets.forEach((t) => t.classList.remove("hit", "safe"));
      box.dataset.state = "idle";
    }

    function showAll() {
      rows.forEach((row) => row.classList.remove("pending"));
      targets.forEach((t) => t.classList.add("safe"));
      box.dataset.state = "idle";
    }

    function step() {
      if (index >= rows.length) {
        // 一轮结束：外面的东西都没被碰到
        targets.forEach((t) => {
          t.classList.remove("hit");
          t.classList.add("safe");
        });
        box.dataset.state = "idle";
        timer = window.setTimeout(() => {
          reset();
          step();
        }, END_MS);
        return;
      }
      const row = rows[index];
      row.classList.remove("pending");
      box.dataset.state = row.dataset.verdict;
      targets.forEach((t) => t.classList.remove("hit"));
      if (row.dataset.target) {
        const hit = targets.find((t) => t.dataset.target === row.dataset.target);
        if (hit) hit.classList.add("hit");
      }
      index += 1;
      timer = window.setTimeout(step, STEP_MS);
    }

    function play() {
      if (playing) return;
      playing = true;
      toggle.textContent = "暂停";
      step();
    }

    function pause() {
      playing = false;
      window.clearTimeout(timer);
      toggle.textContent = "继续";
    }

    toggle.addEventListener("click", () => (playing ? pause() : play()));
    replay.addEventListener("click", () => {
      window.clearTimeout(timer);
      playing = false;
      reset();
      play();
    });

    if (reduced) {
      // 系统设置了“减少动态效果”：直接显示结果，想看再点重播
      showAll();
      toggle.textContent = "继续";
    } else {
      reset();
      // 滚到看得见的时候才开始放
      const io = new IntersectionObserver(
        (entries) => {
          if (entries.some((e) => e.isIntersecting)) {
            io.disconnect();
            play();
          }
        },
        { threshold: 0.35 }
      );
      io.observe(demo);
    }
  }

  // ---- 复制按钮 ----
  document.querySelectorAll(".code .copy").forEach((button) => {
    button.addEventListener("click", async () => {
      const code = button.parentElement.querySelector("code");
      try {
        await navigator.clipboard.writeText(code.textContent);
        button.textContent = "已复制";
      } catch {
        button.textContent = "复制失败";
      }
      window.setTimeout(() => (button.textContent = "复制"), 1600);
    });
  });
})();
