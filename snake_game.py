"""贪吃蛇小游戏。

玩法：开始后按空格键（或任意方向键）开局，方向键控制移动，
吃到红色食物得 10 分并变长，撞墙或咬到自身则游戏结束；
空格键暂停/继续，结束后按 R 重开、ESC 退出。
"""

import math
import os
import random
import sys

import pygame

# ---------- 网格与窗口常量 ----------
CELL_SIZE = 20        # 每个逻辑网格对应的像素尺寸
GRID_WIDTH = 32       # 横向格子数
GRID_HEIGHT = 24      # 纵向格子数
WINDOW_WIDTH = CELL_SIZE * GRID_WIDTH
WINDOW_HEIGHT = CELL_SIZE * GRID_HEIGHT
SPEED = 10            # 蛇每秒前进的格数
MOVE_INTERVAL_MS = 1000 // SPEED

# ---------- 配色（黑色背景、绿色小蛇） ----------
BLACK = (0, 0, 0)
BG_GRID = (18, 22, 18)       # 极淡的网格线，几乎不抢眼
GREEN = (46, 204, 50)        # 蛇头：鲜亮绿
GREEN_LIGHT = (120, 230, 120)  # 蛇身顶部高光
DARK_GREEN = (22, 140, 40)   # 蛇身主色
DARK_GREEN_ALT = (18, 110, 34)  # 蛇身交替深绿
GREEN_SHADOW = (10, 70, 20)  # 蛇身底部阴影
RED = (220, 60, 60)          # 食物主体
RED_LIGHT = (255, 140, 120)  # 食物高光
LEAF = (80, 180, 90)         # 食物叶子
WHITE = (255, 255, 255)
GRAY = (170, 170, 170)
PANEL_BG = (0, 0, 0, 150)    # 得分面板半透明底

# 高分持久化文件
HIGHSCORE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "highscore.txt"
)

# 方向向量，坐标系 y 轴向下为正
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

# 中文字体候选（常规 / 粗体分别匹配），按优先级排列
_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
)
_FONT_BOLD_CANDIDATES = (
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
)


def load_font(size, bold=False):
    """按路径直接加载中文字体。

    绕过部分 pygame 版本 SysFont 在 Windows 上枚举字体注册表时崩溃的问题；
    所有候选都不存在时回退到内置默认字体，保证游戏仍可启动。
    """
    candidates = _FONT_BOLD_CANDIDATES if bold else _FONT_CANDIDATES
    for font_path in candidates:
        if os.path.isfile(font_path):
            return pygame.font.Font(font_path, size)
    return pygame.font.Font(None, size)


class Snake:
    """蛇：维护身体各节的网格坐标、移动方向与碰撞判定。"""

    def __init__(self):
        center_x = GRID_WIDTH // 2
        center_y = GRID_HEIGHT // 2
        # 初始三节横向排列，蛇头在列表首位
        self.body = [
            (center_x, center_y),
            (center_x - 1, center_y),
            (center_x - 2, center_y),
        ]
        self.direction = RIGHT
        self._pending_direction = RIGHT

    def change_direction(self, new_direction):
        # 缓冲方向而非立即生效：以“当前逻辑帧方向”为准禁止 180° 掉头，
        # 可避免同一帧内连续按键绕过反向限制
        if (new_direction[0] + self.direction[0],
                new_direction[1] + self.direction[1]) == (0, 0):
            return
        self._pending_direction = new_direction

    def next_head(self):
        """提交缓冲方向，并计算下一步蛇头的网格坐标（不改变身体）。"""
        self.direction = self._pending_direction
        head_x, head_y = self.body[0]
        dx, dy = self.direction
        return head_x + dx, head_y + dy

    def advance(self, new_head, grow):
        """前进一步：插入新蛇头；不生长时移除蛇尾以保持长度。"""
        self.body.insert(0, new_head)
        if not grow:
            self.body.pop()

    @staticmethod
    def is_out_of_bounds(position):
        x, y = position
        return not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT)

    def hits_body(self, position, will_grow):
        # 不生长时尾巴会随本次移动让出，因此碰撞检测需排除最后一节，
        # 否则“追进尾巴当前格子”会被误判为自咬
        collision_body = self.body if will_grow else self.body[:-1]
        return position in collision_body

    def draw(self, surface):
        radius = 6
        for index, (x, y) in enumerate(self.body):
            rect = pygame.Rect(
                x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE
            )
            is_head = index == 0
            # 主体：蛇头亮绿，蛇身用深浅交替的绿以区分节段
            if is_head:
                body_color = GREEN
            else:
                body_color = DARK_GREEN if index % 2 == 0 else DARK_GREEN_ALT

            pygame.draw.rect(surface, body_color, rect, border_radius=radius)

            # 顶部高光条：模拟受光面，增强立体感
            highlight = pygame.Rect(rect.x + 2, rect.y + 2, rect.width - 4, 3)
            pygame.draw.rect(surface, GREEN_LIGHT, highlight, border_radius=2)
            # 底部阴影条：模拟背光面
            shadow = pygame.Rect(
                rect.x + 2, rect.y + rect.height - 5, rect.width - 4, 3
            )
            pygame.draw.rect(surface, GREEN_SHADOW, shadow, border_radius=2)

        # 蛇头眼睛叠加在最上层，位置随移动方向调整
        self._draw_head_eyes(surface)

    def _draw_head_eyes(self, surface):
        """根据当前方向在蛇头上绘制朝向眼睛。"""
        x, y = self.body[0]
        cx = x * CELL_SIZE + CELL_SIZE // 2
        cy = y * CELL_SIZE + CELL_SIZE // 2
        dx, dy = self.direction
        # 眼睛沿垂直于行进方向的轴分布，向行进方向偏移
        eye_offset = 4
        eye_radius = 3
        pupil_radius = 1
        forward = 3  # 眼睛向行进方向突出的距离

        # 两个眼睛的中心位置：行进方向为水平时上下分布，垂直时左右分布
        if dx != 0:
            eye1 = (cx + dx * forward, cy - eye_offset)
            eye2 = (cx + dx * forward, cy + eye_offset)
        else:
            eye1 = (cx - eye_offset, cy + dy * forward)
            eye2 = (cx + eye_offset, cy + dy * forward)

        for eye in (eye1, eye2):
            pygame.draw.circle(surface, WHITE, eye, eye_radius)
            # 瞳孔朝行进方向偏移一点，让蛇“看”向移动方向
            pupil = (eye[0] + dx, eye[1] + dy)
            pygame.draw.circle(surface, BLACK, pupil, pupil_radius)


class Food:
    """食物：在不与蛇身重叠的空格中随机生成。"""

    def __init__(self, snake):
        self.position = (0, 0)
        self.respawn(snake)

    def respawn(self, snake):
        # 先枚举全部空格再随机选取，避免反复随机重试的不确定性开销
        occupied = set(snake.body)
        free_cells = [
            (x, y)
            for x in range(GRID_WIDTH)
            for y in range(GRID_HEIGHT)
            if (x, y) not in occupied
        ]
        # 棋盘被蛇填满（通关）时没有可放置的格子
        self.position = random.choice(free_cells) if free_cells else None

    def draw(self, surface):
        if self.position is None:
            return
        x, y = self.position
        cx = x * CELL_SIZE + CELL_SIZE // 2
        cy = y * CELL_SIZE + CELL_SIZE // 2

        # 呼吸缩放：基于时间的正弦波，半径在基础值上下轻微浮动
        base_radius = CELL_SIZE // 2 - 3
        pulse = math.sin(pygame.time.get_ticks() / 280.0) * 1.5
        radius = max(2, base_radius + pulse)

        # 苹果主体
        pygame.draw.circle(surface, RED, (cx, cy + 1), int(radius))
        # 左上高光点，营造水果的光泽感
        pygame.draw.circle(
            surface, RED_LIGHT,
            (cx - radius // 3, cy - radius // 3), max(1, radius // 4),
        )
        # 顶部茎
        stem_top = (cx, cy - radius)
        pygame.draw.line(surface, (120, 70, 30), stem_top, (cx, cy - radius + 3), 2)
        # 叶子：用小椭圆/圆近似
        pygame.draw.circle(
            surface, LEAF,
            (cx + 4, cy - radius - 1), 3,
        )


class Game:
    """游戏主控：按“事件处理 / 状态更新 / 绘制”三段式组织主循环。"""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("贪吃蛇")
        self.clock = pygame.time.Clock()
        # 直接加载 Windows 自带的微软雅黑/黑体，保证中文得分与提示正常显示
        self.font = load_font(22)
        self.big_font = load_font(52, bold=True)
        self.small_font = load_font(18)
        # 结束/暂停遮罩只创建一次，避免每帧重复申请同样大小的 Surface
        self._overlay = pygame.Surface(
            (WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA
        )
        self._overlay.fill((0, 0, 0, 165))
        # 预渲染棋盘背景（黑色 + 极淡网格线），每帧直接 blit，省去重复画线
        self._background = self._build_background()
        # 得分面板的圆角半透明底板，尺寸足以容纳“得分”与“最高分”
        self._score_panel = self._build_score_panel()
        # 最高分：从本地文件读取，不存在则为 0
        self.high_score = self._load_high_score()
        # 记录上一帧物理按键状态，用于按下沿检测（绕开中文输入法对字母键的拦截）
        self._prev_keys = pygame.key.get_pressed()
        self.reset()

    def _build_background(self):
        """预渲染带网格线的纯黑背景，提升绘制效率。"""
        bg = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        bg.fill(BLACK)
        for gx in range(1, GRID_WIDTH):
            x = gx * CELL_SIZE
            pygame.draw.line(bg, BG_GRID, (x, 0), (x, WINDOW_HEIGHT))
        for gy in range(1, GRID_HEIGHT):
            y = gy * CELL_SIZE
            pygame.draw.line(bg, BG_GRID, (0, y), (WINDOW_WIDTH, y))
        return bg

    def _build_score_panel(self):
        """创建得分面板的圆角半透明底板。"""
        panel_w, panel_h = 210, 64
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill(PANEL_BG)
        # 圆角通过 mask 模拟：把四角的小方块清透明
        corner = 8
        for (cx, cy) in (
            (0, 0), (panel_w - corner, 0),
            (0, panel_h - corner), (panel_w - corner, panel_h - corner),
        ):
            pygame.draw.rect(panel, (0, 0, 0, 0), (cx, cy, corner, corner))
        return panel

    @staticmethod
    def _load_high_score():
        try:
            with open(HIGHSCORE_FILE, "r", encoding="utf-8") as f:
                return int(f.read().strip() or "0")
        except (FileNotFoundError, ValueError):
            return 0

    def _save_high_score(self):
        try:
            with open(HIGHSCORE_FILE, "w", encoding="utf-8") as f:
                f.write(str(self.high_score))
        except OSError:
            pass  # 写入失败时不影响游戏

    def reset(self):
        self.snake = Snake()
        self.food = Food(self.snake)
        self.score = 0
        self.is_game_over = False
        self.is_paused = False
        # 开局先静止等待，避免窗口尚未获得焦点时蛇自行撞墙
        self._waiting_start = True
        self.is_paused = True
        self._move_elapsed_ms = 0

    def run(self):
        while True:
            # 渲染固定 60 FPS；移动按累计时间独立 tick，二者解耦
            delta_ms = self.clock.tick(60)
            self.handle_events()
            self._poll_action_keys()
            # 暂停/结束时冻结逻辑计时，恢复后不会补偿停顿期间的移动
            if not self.is_game_over and not self.is_paused:
                self._move_elapsed_ms += delta_ms
                if self._move_elapsed_ms >= MOVE_INTERVAL_MS:
                    self._move_elapsed_ms -= MOVE_INTERVAL_MS
                    self.update()
            self.draw()

    def handle_events(self):
        # 输入双通道：
        # - 方向键、R 重启：用 KEYDOWN 事件（英文输入法下即时响应）
        # - 字母键（R/Q）与空格：同时在 _poll_action_keys 用物理键按下沿兜底，
        #   覆盖中文输入法吞掉 KEYDOWN 的场景。reset 幂等，双通道不冲突。
        direction_map = {
            pygame.K_UP: UP,
            pygame.K_DOWN: DOWN,
            pygame.K_LEFT: LEFT,
            pygame.K_RIGHT: RIGHT,
        }
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            if event.type != pygame.KEYDOWN:
                continue

            # 结束态按 R：KEYDOWN 通道触发重启（与物理键通道互为兜底）
            if self.is_game_over and event.key == pygame.K_r:
                self.reset()
                continue

            if event.key not in direction_map:
                continue

            # 等待开局时按任意方向键也可直接开始，并同步应用该方向
            if self._waiting_start:
                self._waiting_start = False
                self.is_paused = False
                self.snake.change_direction(direction_map[event.key])
                continue

            # 暂停/结束期间屏蔽方向输入，避免恢复瞬间执行积压的转向意图
            if self.is_paused or self.is_game_over:
                continue

            self.snake.change_direction(direction_map[event.key])

    def _poll_action_keys(self):
        """用物理键状态做按下沿检测，绕开中文输入法对字母键事件的吞掉。"""
        current = pygame.key.get_pressed()

        # 空格键：开始 / 暂停切换
        if self._key_pressed_edge(current, pygame.K_SPACE):
            if not self.is_game_over:
                self._waiting_start = False
                self.is_paused = not self.is_paused

        # R 键：仅在结束态重新开始
        if self._key_pressed_edge(current, pygame.K_r) and self.is_game_over:
            self.reset()

        # ESC / Q：退出
        if (self._key_pressed_edge(current, pygame.K_ESCAPE)
                or self._key_pressed_edge(current, pygame.K_q)):
            self.quit()

        self._prev_keys = current

    def _key_pressed_edge(self, current, key):
        """按下沿：当前帧按下 且 上一帧未按下，确保一次按键只触发一次。"""
        return current[key] and not self._prev_keys[key]

    def update(self):
        new_head = self.snake.next_head()
        will_grow = new_head == self.food.position

        # 撞墙或自咬：游戏结束，身体不再推进
        if (self.snake.is_out_of_bounds(new_head)
                or self.snake.hits_body(new_head, will_grow)):
            self.is_game_over = True
            # 刷新并持久化最高分
            if self.score > self.high_score:
                self.high_score = self.score
                self._save_high_score()
            return

        self.snake.advance(new_head, will_grow)
        if will_grow:
            self.score += 10
            self.food.respawn(self.snake)

    def draw(self):
        # 预渲染的棋盘背景直接贴，省去每帧画网格线的开销
        self.screen.blit(self._background, (0, 0))
        self.food.draw(self.screen)
        self.snake.draw(self.screen)
        self._draw_score()
        if self.is_game_over:
            self._draw_game_over()
        elif self.is_paused:
            self._draw_paused()
        pygame.display.flip()

    def _draw_score(self):
        # 圆角半透明底板，左上角留一点边距
        panel_x, panel_y = 10, 10
        self.screen.blit(self._score_panel, (panel_x, panel_y))
        # 若破纪录则用绿色强调当前得分
        score_color = GREEN_LIGHT if self.score > 0 and self.score >= self.high_score else WHITE
        score_surface = self.font.render(f"得分  {self.score}", True, score_color)
        high_surface = self.small_font.render(
            f"最高分  {self.high_score}", True, GRAY
        )
        self.screen.blit(score_surface, (panel_x + 14, panel_y + 8))
        self.screen.blit(high_surface, (panel_x + 14, panel_y + 36))

    def _draw_text_shadow(self, surface, font, text, color, center):
        """带阴影的居中文字：先绘制偏移的深色阴影再绘制主文字，增强立体感。"""
        shadow = font.render(text, True, (0, 0, 0))
        main = font.render(text, True, color)
        rect = main.get_rect(center=center)
        shadow_rect = shadow.get_rect(center=(center[0] + 2, center[1] + 2))
        surface.blit(shadow, shadow_rect)
        surface.blit(main, rect)

    def _draw_game_over(self):
        self.screen.blit(self._overlay, (0, 0))
        cx, cy = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
        self._draw_text_shadow(self.screen, self.big_font, "游戏结束", RED, (cx, cy - 40))
        final = (
            f"最终得分  {self.score}        最高分  {self.high_score}"
        )
        self._draw_text_shadow(self.screen, self.font, final, WHITE, (cx, cy + 6))
        self._draw_text_shadow(
            self.screen, self.small_font,
            "按 R 重新开始，按 ESC 退出", GRAY, (cx, cy + 42),
        )

    def _draw_paused(self):
        # 半透明遮罩保留当前棋盘画面，并提示游戏已冻结
        self.screen.blit(self._overlay, (0, 0))
        cx, cy = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
        if self._waiting_start:
            message_text = "贪 吃 蛇"
            hint_text = "按空格键或方向键开始，ESC 退出"
        else:
            message_text = "已暂停"
            hint_text = "按空格键继续，按 ESC 退出"
        self._draw_text_shadow(
            self.screen, self.big_font, message_text, GREEN_LIGHT, (cx, cy - 30),
        )
        self._draw_text_shadow(
            self.screen, self.font, hint_text, GRAY, (cx, cy + 24),
        )

    @staticmethod
    def quit():
        pygame.quit()
        sys.exit()


def main():
    Game().run()


if __name__ == "__main__":
    main()
