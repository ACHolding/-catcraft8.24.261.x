#!/usr/bin/env python3
"""
Cat Craft 0.1 — Infdev-style voxel sandbox
Branding: AC Kondo / Cat's Craft
Engine: pygame-ce | Files: OFF (RAM only) | Projection: software math
"""

from __future__ import annotations

import math
import random
import sys
from typing import Dict, List, Optional, Tuple

import pygame

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TITLE = "Cat Craft 0.1"
BRAND = "AC Kondo / Cat's Craft"
WIDTH, HEIGHT = 854, 480
FPS = 60
FOV = 70.0
NEAR_Z = 0.08
RENDER_DIST = 18
REACH = 5.5

# "Windows XP" nostalgic pace — a touch slower than modern MC
WALK_SPEED = 3.4
MOUSE_SENS = 0.12
GRAVITY = 22.0
JUMP_VEL = 7.2
PLAYER_H = 1.62
PLAYER_EYE = 1.52
PLAYER_W = 0.30

# Block IDs
AIR, GRASS, DIRT, STONE, COBBLE, PLANKS, WOOD, LEAVES, SAND, WATER = range(10)

BLOCK_NAMES = {
    GRASS: "Grass",
    DIRT: "Dirt",
    STONE: "Stone",
    COBBLE: "Cobblestone",
    PLANKS: "Planks",
    WOOD: "Wood",
    LEAVES: "Leaves",
    SAND: "Sand",
}

# Face colors (top, side, bottom) — Infdev-ish muted palette
BLOCK_COLORS: Dict[int, Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]] = {
    GRASS:  ((92, 148, 58), (112, 88, 58), (88, 64, 42)),
    DIRT:   ((112, 88, 58), (112, 88, 58), (88, 64, 42)),
    STONE:  ((128, 128, 128), (112, 112, 112), (96, 96, 96)),
    COBBLE: ((110, 110, 110), (96, 96, 96), (82, 82, 82)),
    PLANKS: ((168, 136, 84), (148, 118, 70), (128, 100, 58)),
    WOOD:   ((96, 76, 46), (96, 76, 46), (72, 56, 34)),
    LEAVES: ((58, 118, 42), (48, 98, 36), (40, 82, 30)),
    SAND:   ((214, 198, 146), (198, 182, 132), (176, 160, 112)),
    WATER:  ((56, 96, 178), (48, 84, 158), (40, 72, 138)),
}

# Cube face definitions: (normal axis, sign, vertex indices into 8 corners)
# Corners: 0:--- 1:+-- 2:++- 3:-+- 4:--+ 5:+-+ 6:+++ 7:-++
FACES = (
    # +Y top
    (1, 1, (4, 5, 6, 7), 0),
    # -Y bottom
    (1, -1, (0, 3, 2, 1), 2),
    # +Z front
    (2, 1, (1, 2, 6, 5), 1),
    # -Z back
    (2, -1, (0, 4, 7, 3), 1),
    # +X right
    (0, 1, (1, 5, 6, 2), 1),
    # -X left
    (0, -1, (0, 3, 7, 4), 1),
)

FACE_OFFSETS = (
    (0, 1, 0),
    (0, -1, 0),
    (0, 0, 1),
    (0, 0, -1),
    (1, 0, 0),
    (-1, 0, 0),
)

Vec3 = Tuple[float, float, float]
BlockPos = Tuple[int, int, int]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def shade(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    return (
        max(0, min(255, int(color[0] * factor))),
        max(0, min(255, int(color[1] * factor))),
        max(0, min(255, int(color[2] * factor))),
    )


# Infdev GUI uses logical 427×240 at scale 2 on 854×480
GUI_SCALE = 2


def _dirt_tile_16(seed: int = 7) -> pygame.Surface:
    """Procedural 16×16 dirt matching classic terrain.png dirt."""
    rng = random.Random(seed)
    tile = pygame.Surface((16, 16))
    base = (134, 96, 67)
    for y in range(16):
        for x in range(16):
            n = rng.random()
            if n < 0.12:
                c = (96, 66, 45)
            elif n < 0.28:
                c = (112, 78, 52)
            elif n < 0.55:
                c = (128, 90, 60)
            elif n < 0.78:
                c = (140, 100, 70)
            else:
                c = (152, 110, 78)
            # Slight vignette like real dirt tex
            if x == 0 or y == 0 or x == 15 or y == 15:
                c = shade(c, 0.88)
            tile.set_at((x, y), c)
    # A few darker pebbles
    for _ in range(6):
        px, py = rng.randint(1, 14), rng.randint(1, 14)
        tile.set_at((px, py), shade(base, 0.55))
    return tile


def make_dirt_surface(w: int, h: int, seed: int = 7) -> pygame.Surface:
    """
    Infdev title background: tiled dirt, scaled 2×, then darkened.
    Minecraft multiplies the dirt panorama by ~0.25 for the menu.
    """
    tile = _dirt_tile_16(seed)
    tw = 16 * GUI_SCALE
    tile2 = pygame.Surface((tw, tw))
    pygame.transform.scale(tile, (tw, tw), tile2)
    big = pygame.Surface((w, h))
    for y in range(0, h, tw):
        for x in range(0, w, tw):
            big.blit(tile2, (x, y))
    dark = pygame.Surface((w, h))
    dark.fill((64, 64, 64))
    big.blit(dark, (0, 0), special_flags=pygame.BLEND_MULT)
    return big


def _pixel_font(size: int) -> pygame.font.Font:
    """Prefer a chunky font; fall back to default."""
    for name in ("Courier New", "Consolas", "Lucida Console", "dejavusansmono"):
        try:
            f = pygame.font.SysFont(name, size, bold=True)
            if f:
                return f
        except Exception:
            pass
    return pygame.font.SysFont(None, size, bold=True)


def _render_mc_text(font: pygame.font.Font, text: str, color, shadow: bool = True) -> pygame.Surface:
    """Minecraft-style text: 1px black drop shadow, then optional 2× nearest scale."""
    raw = font.render(text, False, color)
    if shadow:
        sh = font.render(text, False, (0, 0, 0))
        out = pygame.Surface((raw.get_width() + 1, raw.get_height() + 1), pygame.SRCALPHA)
        out.blit(sh, (1, 1))
        out.blit(raw, (0, 0))
    else:
        out = raw.convert_alpha()
    return out


def make_logo_surface(text: str = "Cat Craft") -> pygame.Surface:
    """
    Infdev-era logo: large extruded title (cream face, dark 3D sides).
    Generated entirely in RAM — no assets.
    """
    font = _pixel_font(64)
    # Face color ~ classic logo cream/yellow-white
    face = (255, 255, 255)
    edge = (64, 40, 16)
    # Deep extrusion layers
    layers = 6
    base = font.render(text, False, face)
    w, h = base.get_width() + layers + 4, base.get_height() + layers + 4
    logo = pygame.Surface((w, h), pygame.SRCALPHA)
    # Bottom-right extrusion (dark)
    for i in range(layers, 0, -1):
        t = i / layers
        col = shade((90, 55, 25), 0.55 + 0.35 * (1.0 - t))
        logo.blit(font.render(text, False, col), (2 + i, 2 + i))
    # Black outline
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
        logo.blit(font.render(text, False, (0, 0, 0)), (2 + ox, 2 + oy))
    # Main face
    logo.blit(font.render(text, False, face), (2, 2))
    # Subtle dirt-noise on face for that terrain-logo feel
    rng = random.Random(3)
    face_rect = pygame.Rect(2, 2, base.get_width(), base.get_height())
    noise = pygame.Surface((face_rect.w, face_rect.h), pygame.SRCALPHA)
    for _ in range(face_rect.w * face_rect.h // 14):
        nx = rng.randint(0, face_rect.w - 1)
        ny = rng.randint(0, face_rect.h - 1)
        a = rng.randint(10, 40)
        noise.set_at((nx, ny), (180, 140, 80, a))
    logo.blit(noise, (2, 2))
    return logo


def make_button_surfaces(
    font: pygame.font.Font,
    label: str,
    w: int = 200 * GUI_SCALE,
    h: int = 20 * GUI_SCALE,
    disabled: bool = False,
):
    """
    Classic Minecraft widgets.png button:
    idle gray stone, hover yellow text, disabled dark — generated in RAM.
    """
    states = {}
    specs = [
        ("idle", (110, 110, 110), (224, 224, 224)),
        ("hover", (128, 128, 168), (255, 255, 160)),
        ("disabled", (72, 72, 72), (96, 96, 96)),
    ]
    for name, base, text_col in specs:
        surf = pygame.Surface((w, h))
        surf.fill(base)
        pygame.draw.rect(surf, (0, 0, 0), (0, 0, w, h), 1)
        if name != "disabled":
            pygame.draw.line(surf, (255, 255, 255), (1, 1), (w - 2, 1))
            pygame.draw.line(surf, (255, 255, 255), (1, 1), (1, h - 2))
            pygame.draw.line(surf, (55, 55, 55), (1, h - 2), (w - 2, h - 2))
            pygame.draw.line(surf, (55, 55, 55), (w - 2, 1), (w - 2, h - 2))
        col = text_col if not disabled else (96, 96, 96)
        label_s = _render_mc_text(font, label, col)
        tx = (w - label_s.get_width()) // 2
        ty = (h - label_s.get_height()) // 2 - 1
        surf.blit(label_s, (tx, ty))
        states[name] = surf
    if disabled:
        d = states["disabled"]
        return d, d, d
    return states["idle"], states["hover"], states["disabled"]


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------
class World:
    def __init__(self, size: int = 48, seed: Optional[int] = None):
        self.size = size
        self.seed = seed if seed is not None else random.randint(0, 2**31 - 1)
        self.rng = random.Random(self.seed)
        self.blocks: Dict[BlockPos, int] = {}
        self._generate_flat()

    def _generate_flat(self) -> None:
        """Infdev-style flat terrain: dirt base, patchy grass top."""
        half = self.size // 2
        ground_y = 4
        for x in range(-half, half):
            for z in range(-half, half):
                # Stone base
                for y in range(0, 3):
                    self.blocks[(x, y, z)] = STONE
                # Dirt layer
                self.blocks[(x, 3, z)] = DIRT
                # Grass / dirt / rare sand patches on surface
                r = self.rng.random()
                if r < 0.78:
                    self.blocks[(x, ground_y, z)] = GRASS
                elif r < 0.93:
                    self.blocks[(x, ground_y, z)] = DIRT
                else:
                    self.blocks[(x, ground_y, z)] = SAND
                # Sparse "trees" — Infdev charm
                if self.rng.random() < 0.012 and self.get(x, ground_y, z) == GRASS:
                    self._place_tree(x, ground_y + 1, z)

    def _place_tree(self, x: int, y: int, z: int) -> None:
        h = self.rng.randint(3, 5)
        for i in range(h):
            self.blocks[(x, y + i, z)] = WOOD
        top = y + h - 1
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                for dy in range(0, 3):
                    if abs(dx) == 2 and abs(dz) == 2 and self.rng.random() < 0.55:
                        continue
                    if dx == 0 and dz == 0 and dy < 2:
                        continue
                    self.blocks[(x + dx, top + dy, z + dz)] = LEAVES

    def get(self, x: int, y: int, z: int) -> int:
        return self.blocks.get((x, y, z), AIR)

    def set(self, x: int, y: int, z: int, bid: int) -> None:
        key = (x, y, z)
        if bid == AIR:
            self.blocks.pop(key, None)
        else:
            self.blocks[key] = bid

    def solid(self, x: int, y: int, z: int) -> bool:
        b = self.get(x, y, z)
        return b != AIR and b != WATER


# ---------------------------------------------------------------------------
# Camera / Player
# ---------------------------------------------------------------------------
class Player:
    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0
        self.yaw = 0.0  # degrees, 0 = -Z
        self.pitch = 0.0
        self.on_ground = False
        self.hotbar = [GRASS, DIRT, STONE, COBBLE, PLANKS, WOOD, LEAVES, SAND]
        self.slot = 0

    @property
    def selected(self) -> int:
        return self.hotbar[self.slot]

    def eye(self) -> Vec3:
        return (self.x, self.y + PLAYER_EYE, self.z)

    def look_dir(self) -> Vec3:
        yaw_r = math.radians(self.yaw)
        pitch_r = math.radians(self.pitch)
        cp = math.cos(pitch_r)
        return (
            math.sin(yaw_r) * cp,
            -math.sin(pitch_r),
            -math.cos(yaw_r) * cp,
        )


# ---------------------------------------------------------------------------
# Raycast
# ---------------------------------------------------------------------------
def raycast(world: World, origin: Vec3, direction: Vec3, max_dist: float = REACH):
    """DDA voxel raycast. Returns (hit_pos, place_pos, face_normal) or None."""
    ox, oy, oz = origin
    dx, dy, dz = direction
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-9:
        return None
    dx, dy, dz = dx / length, dy / length, dz / length

    x, y, z = math.floor(ox), math.floor(oy), math.floor(oz)
    step_x = 1 if dx > 0 else -1 if dx < 0 else 0
    step_y = 1 if dy > 0 else -1 if dy < 0 else 0
    step_z = 1 if dz > 0 else -1 if dz < 0 else 0

    t_delta_x = abs(1.0 / dx) if dx != 0 else 1e30
    t_delta_y = abs(1.0 / dy) if dy != 0 else 1e30
    t_delta_z = abs(1.0 / dz) if dz != 0 else 1e30

    if dx > 0:
        t_max_x = (math.floor(ox) + 1 - ox) * t_delta_x
    elif dx < 0:
        t_max_x = (ox - math.floor(ox)) * t_delta_x
    else:
        t_max_x = 1e30

    if dy > 0:
        t_max_y = (math.floor(oy) + 1 - oy) * t_delta_y
    elif dy < 0:
        t_max_y = (oy - math.floor(oy)) * t_delta_y
    else:
        t_max_y = 1e30

    if dz > 0:
        t_max_z = (math.floor(oz) + 1 - oz) * t_delta_z
    elif dz < 0:
        t_max_z = (oz - math.floor(oz)) * t_delta_z
    else:
        t_max_z = 1e30

    dist = 0.0
    face = (0, 0, 0)
    while dist <= max_dist:
        if world.solid(x, y, z):
            px, py, pz = x - face[0], y - face[1], z - face[2]
            return (x, y, z), (px, py, pz), face
        if t_max_x < t_max_y:
            if t_max_x < t_max_z:
                x += step_x
                dist = t_max_x
                t_max_x += t_delta_x
                face = (-step_x, 0, 0)
            else:
                z += step_z
                dist = t_max_z
                t_max_z += t_delta_z
                face = (0, 0, -step_z)
        else:
            if t_max_y < t_max_z:
                y += step_y
                dist = t_max_y
                t_max_y += t_delta_y
                face = (0, -step_y, 0)
            else:
                z += step_z
                dist = t_max_z
                t_max_z += t_delta_z
                face = (0, 0, -step_z)
    return None


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------
def _aabb_blocked(world: World, px: float, py: float, pz: float) -> bool:
    hw = PLAYER_W
    for bx in range(math.floor(px - hw), math.floor(px + hw) + 1):
        for by in range(math.floor(py), math.floor(py + PLAYER_H - 0.01) + 1):
            for bz in range(math.floor(pz - hw), math.floor(pz + hw) + 1):
                if world.solid(bx, by, bz):
                    return True
    return False


def collide_move(world: World, player: Player, dx: float, dy: float, dz: float) -> None:
    """AABB sweep against solid blocks — XP-era floaty feel."""
    px, py, pz = player.x, player.y, player.z

    if dx != 0:
        nx = px + dx
        if not _aabb_blocked(world, nx, py, pz):
            px = nx
        else:
            player.vx = 0.0

    if dz != 0:
        nz = pz + dz
        if not _aabb_blocked(world, px, py, nz):
            pz = nz
        else:
            player.vz = 0.0

    player.on_ground = False
    if dy != 0:
        ny = py + dy
        if not _aabb_blocked(world, px, ny, pz):
            py = ny
        else:
            if dy < 0:
                player.on_ground = True
                py = math.floor(py + dy) + 1.0
            else:
                py = math.ceil(py + dy + PLAYER_H) - PLAYER_H - 0.001
            player.vy = 0.0

    player.x, player.y, player.z = px, py, pz


def update_player(world: World, player: Player, keys, dt: float) -> None:
    yaw_r = math.radians(player.yaw)
    forward = (math.sin(yaw_r), 0.0, -math.cos(yaw_r))
    right = (math.cos(yaw_r), 0.0, math.sin(yaw_r))

    mx = mz = 0.0
    if keys[pygame.K_w]:
        mx += forward[0]
        mz += forward[2]
    if keys[pygame.K_s]:
        mx -= forward[0]
        mz -= forward[2]
    if keys[pygame.K_d]:
        mx += right[0]
        mz += right[2]
    if keys[pygame.K_a]:
        mx -= right[0]
        mz -= right[2]

    length = math.sqrt(mx * mx + mz * mz)
    if length > 0:
        mx /= length
        mz /= length
        # Mild XP-era accel feel
        speed = WALK_SPEED * (1.35 if keys[pygame.K_LSHIFT] else 1.0)
        player.vx = mx * speed
        player.vz = mz * speed
    else:
        player.vx *= 0.6
        player.vz *= 0.6
        if abs(player.vx) < 0.01:
            player.vx = 0.0
        if abs(player.vz) < 0.01:
            player.vz = 0.0

    if keys[pygame.K_SPACE] and player.on_ground:
        player.vy = JUMP_VEL
        player.on_ground = False

    player.vy -= GRAVITY * dt
    collide_move(world, player, player.vx * dt, player.vy * dt, player.vz * dt)

    # Void / fall reset (no save — just respawn in RAM)
    if player.y < -20:
        player.x = 0.5
        player.y = 8.0
        player.z = 0.5
        player.vx = player.vy = player.vz = 0.0


# ---------------------------------------------------------------------------
# Software 3D renderer
# ---------------------------------------------------------------------------
class Renderer:
    def __init__(self, width: int, height: int):
        self.w = width
        self.h = height
        self.cx = width // 2
        self.cy = height // 2
        self.focal = (height * 0.5) / math.tan(math.radians(FOV * 0.5))
        self.render_dist = RENDER_DIST
        self.sky = pygame.Surface((width, height))
        sky_top = (140, 180, 255)
        sky_bot = (190, 210, 255)
        for y in range(height):
            t = y / height
            r = int(sky_top[0] + (sky_bot[0] - sky_top[0]) * t)
            g = int(sky_top[1] + (sky_bot[1] - sky_top[1]) * t)
            b = int(sky_top[2] + (sky_bot[2] - sky_top[2]) * t)
            pygame.draw.line(self.sky, (r, g, b), (0, y), (width, y))

    def project(self, cam: Player, wx: float, wy: float, wz: float):
        """World → camera → screen. Returns (sx, sy, depth) or None if behind."""
        ex, ey, ez = cam.eye()
        x = wx - ex
        y = wy - ey
        z = wz - ez
        yaw_r = math.radians(cam.yaw)
        pitch_r = math.radians(cam.pitch)
        cos_y, sin_y = math.cos(yaw_r), math.sin(yaw_r)
        rx = x * cos_y + z * sin_y
        rz = -x * sin_y + z * cos_y
        cos_p, sin_p = math.cos(pitch_r), math.sin(pitch_r)
        ry = y * cos_p - rz * sin_p
        rz2 = y * sin_p + rz * cos_p
        depth = -rz2
        if depth < NEAR_Z:
            return None
        sx = self.cx + (rx * self.focal) / depth
        sy = self.cy - (ry * self.focal) / depth
        return sx, sy, depth

    def draw_sky(self, surface: pygame.Surface) -> None:
        surface.blit(self.sky, (0, 0))

    def collect_faces(self, world: World, cam: Player):
        """Gather visible block faces near the camera, with depth."""
        faces_out = []
        ex, ey, ez = cam.eye()
        ix, iy, iz = int(ex), int(ey), int(ez)
        rd = self.render_dist
        rd2 = rd * rd

        # Ambient face shade multipliers
        face_light = (1.0, 0.55, 0.75, 0.75, 0.85, 0.65)  # top,bot,N/S-ish,E/W

        for bx in range(ix - rd, ix + rd + 1):
            for bz in range(iz - rd, iz + rd + 1):
                dx = bx + 0.5 - ex
                dz = bz + 0.5 - ez
                if dx * dx + dz * dz > rd2:
                    continue
                for by in range(max(0, iy - rd), iy + rd + 1):
                    bid = world.get(bx, by, bz)
                    if bid == AIR:
                        continue
                    colors = BLOCK_COLORS.get(bid)
                    if not colors:
                        continue
                    # Corner positions
                    corners = (
                        (bx, by, bz),
                        (bx + 1, by, bz),
                        (bx + 1, by, bz + 1),
                        (bx, by, bz + 1),
                        (bx, by + 1, bz),
                        (bx + 1, by + 1, bz),
                        (bx + 1, by + 1, bz + 1),
                        (bx, by + 1, bz + 1),
                    )
                    for fi, (axis, sign, idxs, color_i) in enumerate(FACES):
                        ox, oy, oz = FACE_OFFSETS[fi]
                        nb = world.get(bx + ox, by + oy, bz + oz)
                        if nb != AIR and nb != WATER:
                            continue  # occluded
                        # Project corners
                        pts = []
                        depth_sum = 0.0
                        ok = True
                        for ci in idxs:
                            wx, wy, wz = corners[ci]
                            p = self.project(cam, wx, wy, wz)
                            if p is None:
                                ok = False
                                break
                            pts.append((p[0], p[1]))
                            depth_sum += p[2]
                        if not ok or len(pts) < 3:
                            continue
                        avg_d = depth_sum / 4.0
                        # Back-face rough cull via camera-to-center vs normal
                        cx = bx + 0.5 + ox * 0.5
                        cy = by + 0.5 + oy * 0.5
                        cz = bz + 0.5 + oz * 0.5
                        vx, vy, vz = cx - ex, cy - ey, cz - ez
                        if vx * ox + vy * oy + vz * oz >= 0:
                            continue
                        col = shade(colors[color_i], face_light[fi])
                        # Distance fog (soft Infdev haze)
                        fog = clamp(1.0 - (avg_d / (rd * 1.15)), 0.15, 1.0)
                        col = shade(col, fog)
                        faces_out.append((avg_d, pts, col))
        faces_out.sort(key=lambda f: -f[0])  # far → near
        return faces_out

    def render_world(self, surface: pygame.Surface, world: World, cam: Player) -> None:
        self.draw_sky(surface)
        faces = self.collect_faces(world, cam)
        for _, pts, col in faces:
            # Clip trivial off-screen
            if all(p[0] < -50 or p[0] > self.w + 50 or p[1] < -50 or p[1] > self.h + 50 for p in pts):
                continue
            try:
                pygame.draw.polygon(surface, col, pts)
                # Subtle edge for that early-Minecraft look
                pygame.draw.polygon(surface, shade(col, 0.72), pts, 1)
            except Exception:
                pass

    def draw_crosshair(self, surface: pygame.Surface) -> None:
        c = (240, 240, 240)
        x, y = self.cx, self.cy
        pygame.draw.line(surface, c, (x - 8, y), (x + 8, y), 1)
        pygame.draw.line(surface, c, (x, y - 8), (x, y + 8), 1)

    def draw_hotbar(self, surface: pygame.Surface, player: Player, font: pygame.font.Font) -> None:
        slot_w, slot_h = 36, 36
        n = len(player.hotbar)
        total = n * slot_w + (n - 1) * 2
        x0 = (self.w - total) // 2
        y0 = self.h - slot_h - 10
        for i, bid in enumerate(player.hotbar):
            x = x0 + i * (slot_w + 2)
            rect = pygame.Rect(x, y0, slot_w, slot_h)
            pygame.draw.rect(surface, (48, 48, 48), rect)
            pygame.draw.rect(surface, (220, 220, 220) if i == player.slot else (100, 100, 100), rect, 2)
            cols = BLOCK_COLORS[bid]
            inner = pygame.Rect(x + 6, y0 + 6, slot_w - 12, slot_h - 12)
            pygame.draw.rect(surface, cols[0], inner)
            pygame.draw.rect(surface, cols[1], (inner.x, inner.bottom - 6, inner.w, 6))
        name = BLOCK_NAMES.get(player.selected, "")
        label = font.render(name, True, (255, 255, 255))
        surface.blit(label, ((self.w - label.get_width()) // 2, y0 - 18))


# ---------------------------------------------------------------------------
# Menu / Options / Game states
# ---------------------------------------------------------------------------
STATE_MENU = "menu"
STATE_OPTIONS = "options"
STATE_PLAY = "play"


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(f"{TITLE} — {BRAND}")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        # Infdev GUI font (~8px bitmap look, drawn at scale)
        self.font_gui = _pixel_font(16)
        self.font = _pixel_font(16)
        self.font_sm = _pixel_font(14)
        self.font_title = _pixel_font(48)
        self.font_brand = _pixel_font(14)

        self.dirt_bg = make_dirt_surface(WIDTH, HEIGHT)
        self.logo = make_logo_surface("Cat Craft")
        self.state = STATE_MENU
        self.world: Optional[World] = None
        self.player: Optional[Player] = None
        self.renderer = Renderer(WIDTH, HEIGHT)
        self.mouse_captured = False
        self.show_debug = False
        self.render_dist_opt = RENDER_DIST
        self.sens_opt = MOUSE_SENS
        self.msg = ""
        self.msg_timer = 0.0

        # Infdev / early-Alpha GuiMainMenu layout (logical coords × GUI_SCALE)
        # width/2 - 100, height/4 + 48  →  Singleplayer
        # width/2 - 100, height/4 + 72  →  Multiplayer (disabled)
        # Options... / Quit Game side-by-side at height/4 + 132
        gs = GUI_SCALE
        lw, lh = WIDTH // gs, HEIGHT // gs  # logical 427×240
        btn_w, btn_h = 200 * gs, 20 * gs
        half_w = 98 * gs
        cx = WIDTH // 2
        y0 = (lh // 4 + 48) * gs
        y1 = (lh // 4 + 72) * gs
        y2 = (lh // 4 + 120 + 12) * gs

        self.btn_single = pygame.Rect(cx - 100 * gs, y0, btn_w, btn_h)
        self.btn_multi = pygame.Rect(cx - 100 * gs, y1, btn_w, btn_h)
        self.btn_opt = pygame.Rect(cx - 100 * gs, y2, half_w, btn_h)
        self.btn_quit = pygame.Rect(cx + 2 * gs, y2, half_w, btn_h)
        self.btn_back = pygame.Rect(cx - 100 * gs, y2, btn_w, btn_h)

        # Keep aliases used elsewhere
        self.btn_gen = self.btn_single

        self._btn_cache = {
            "Singleplayer": make_button_surfaces(self.font_gui, "Singleplayer"),
            "Multiplayer": make_button_surfaces(self.font_gui, "Multiplayer", disabled=True),
            "Options...": make_button_surfaces(self.font_gui, "Options...", w=half_w),
            "Quit Game": make_button_surfaces(self.font_gui, "Quit Game", w=half_w),
            "Done": make_button_surfaces(self.font_gui, "Done"),
            "Render Distance -": make_button_surfaces(self.font_gui, "Render Distance -"),
            "Render Distance +": make_button_surfaces(self.font_gui, "Render Distance +"),
            "Mouse Sensitivity -": make_button_surfaces(self.font_gui, "Mouse Sensitivity -"),
            "Mouse Sensitivity +": make_button_surfaces(self.font_gui, "Mouse Sensitivity +"),
        }

    def toast(self, text: str, t: float = 2.0) -> None:
        self.msg = text
        self.msg_timer = t

    def start_world(self) -> None:
        self.world = World(size=48)
        self.player = Player(0.5, 8.0, 0.5)
        self.state = STATE_PLAY
        self.capture_mouse(True)
        self.toast(f"World seed: {self.world.seed}", 3.0)

    def capture_mouse(self, on: bool) -> None:
        self.mouse_captured = on
        pygame.event.set_grab(on)
        pygame.mouse.set_visible(not on)

    def draw_logo(self, surface: pygame.Surface) -> None:
        """Infdev logo placement — upper third, centered."""
        x = (WIDTH - self.logo.get_width()) // 2
        y = HEIGHT // 4 - self.logo.get_height() // 2 - 8
        surface.blit(self.logo, (x, max(12, y)))

    def draw_button(self, rect: pygame.Rect, label: str, mouse_pos, enabled: bool = True) -> None:
        idle, hover, disabled = self._btn_cache[label]
        if not enabled:
            surf = disabled
        elif rect.collidepoint(mouse_pos):
            surf = hover
        else:
            surf = idle
        self.screen.blit(surf, rect.topleft)

    def draw_menu_footer(self, surface: pygame.Surface) -> None:
        """Version bottom-left, copyright bottom-right — Infdev style."""
        ver = _render_mc_text(self.font_sm, "Cat Craft 0.1", (255, 255, 255))
        surface.blit(ver, (4, HEIGHT - ver.get_height() - 4))
        copy = _render_mc_text(self.font_sm, "Copyright AC Kondo / Cat's Craft. Do not distribute!", (255, 255, 255))
        surface.blit(copy, (WIDTH - copy.get_width() - 4, HEIGHT - copy.get_height() - 4))

    def run_menu(self, events, mouse_pos) -> None:
        # Exact Infdev dirt backdrop (already darkened)
        self.screen.blit(self.dirt_bg, (0, 0))
        self.draw_logo(self.screen)
        self.draw_button(self.btn_single, "Singleplayer", mouse_pos)
        self.draw_button(self.btn_multi, "Multiplayer", mouse_pos, enabled=False)
        self.draw_button(self.btn_opt, "Options...", mouse_pos)
        self.draw_button(self.btn_quit, "Quit Game", mouse_pos)
        self.draw_menu_footer(self.screen)

        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.btn_single.collidepoint(mouse_pos):
                    self.start_world()
                elif self.btn_opt.collidepoint(mouse_pos):
                    self.state = STATE_OPTIONS
                elif self.btn_quit.collidepoint(mouse_pos):
                    pygame.quit()
                    sys.exit(0)
                # Multiplayer intentionally does nothing (Infdev: always grayed out)

    def run_options(self, events, mouse_pos) -> None:
        self.screen.blit(self.dirt_bg, (0, 0))
        hdr = _render_mc_text(self.font_gui, "Options", (255, 255, 255))
        # Scale up header a bit
        hdr2 = pygame.transform.scale(hdr, (hdr.get_width() * 2, hdr.get_height() * 2))
        self.screen.blit(hdr2, ((WIDTH - hdr2.get_width()) // 2, 40))

        info = _render_mc_text(
            self.font_gui,
            f"Render Distance: {self.render_dist_opt}   Sensitivity: {self.sens_opt:.2f}",
            (224, 224, 224),
        )
        self.screen.blit(info, ((WIDTH - info.get_width()) // 2, 120))
        note = _render_mc_text(
            self.font_sm,
            "Files are OFF — settings live in RAM only this session.",
            (200, 200, 200),
        )
        self.screen.blit(note, ((WIDTH - note.get_width()) // 2, 150))

        gs = GUI_SCALE
        cx = WIDTH // 2
        btn_w, btn_h = 200 * gs, 20 * gs
        r_minus = pygame.Rect(cx - 100 * gs, 200, btn_w, btn_h)
        r_plus = pygame.Rect(cx - 100 * gs, 200 + 28 * gs, btn_w, btn_h)
        s_minus = pygame.Rect(cx - 100 * gs, 200 + 56 * gs, btn_w, btn_h)
        s_plus = pygame.Rect(cx - 100 * gs, 200 + 84 * gs, btn_w, btn_h)
        self.draw_button(r_minus, "Render Distance -", mouse_pos)
        self.draw_button(r_plus, "Render Distance +", mouse_pos)
        self.draw_button(s_minus, "Mouse Sensitivity -", mouse_pos)
        self.draw_button(s_plus, "Mouse Sensitivity +", mouse_pos)
        self.draw_button(self.btn_back, "Done", mouse_pos)
        self.draw_menu_footer(self.screen)

        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if r_minus.collidepoint(mouse_pos):
                    self.render_dist_opt = max(8, self.render_dist_opt - 2)
                elif r_plus.collidepoint(mouse_pos):
                    self.render_dist_opt = min(28, self.render_dist_opt + 2)
                elif s_minus.collidepoint(mouse_pos):
                    self.sens_opt = max(0.04, round(self.sens_opt - 0.02, 2))
                elif s_plus.collidepoint(mouse_pos):
                    self.sens_opt = min(0.30, round(self.sens_opt + 0.02, 2))
                elif self.btn_back.collidepoint(mouse_pos):
                    self.state = STATE_MENU

    def run_play(self, events, dt: float) -> None:
        assert self.world and self.player
        self.renderer.render_dist = self.render_dist_opt

        keys = pygame.key.get_pressed()
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.capture_mouse(False)
                    self.state = STATE_MENU
                    self.toast("Returned to menu (world kept in RAM)", 2.5)
                elif e.key == pygame.K_F3:
                    self.show_debug = not self.show_debug
                elif e.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                               pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8):
                    self.player.slot = e.key - pygame.K_1
                elif e.key == pygame.K_e:
                    # Cycle block
                    self.player.slot = (self.player.slot + 1) % len(self.player.hotbar)
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if not self.mouse_captured:
                    self.capture_mouse(True)
                    continue
                hit = raycast(self.world, self.player.eye(), self.player.look_dir())
                if e.button == 1 and hit:  # break
                    hx, hy, hz = hit[0]
                    self.world.set(hx, hy, hz, AIR)
                elif e.button == 3 and hit:  # place
                    px, py, pz = hit[1]
                    # Don't place inside player AABB
                    if not self._overlaps_player(px, py, pz):
                        self.world.set(px, py, pz, self.player.selected)
                elif e.button == 4:
                    self.player.slot = (self.player.slot - 1) % len(self.player.hotbar)
                elif e.button == 5:
                    self.player.slot = (self.player.slot + 1) % len(self.player.hotbar)
            elif e.type == pygame.MOUSEMOTION and self.mouse_captured:
                mx, my = e.rel
                self.player.yaw = (self.player.yaw + mx * self.sens_opt) % 360
                self.player.pitch = clamp(self.player.pitch + my * self.sens_opt, -89, 89)

        if self.mouse_captured:
            update_player(self.world, self.player, keys, dt)

        self.renderer.render_world(self.screen, self.world, self.player)
        self.renderer.draw_crosshair(self.screen)
        self.renderer.draw_hotbar(self.screen, self.player, self.font_sm)

        # HUD
        fps = self.clock.get_fps()
        hud = self.font_sm.render(f"{TITLE}  |  {BRAND}", True, (255, 255, 255))
        self.screen.blit(hud, (6, 4))
        if self.show_debug:
            p = self.player
            dbg = (
                f"FPS: {fps:.0f}  XYZ: {p.x:.1f} / {p.y:.1f} / {p.z:.1f}  "
                f"Yaw: {p.yaw:.0f}  Blocks: {len(self.world.blocks)}"
            )
            self.screen.blit(self.font_sm.render(dbg, True, (220, 255, 220)), (6, 22))

        if self.msg_timer > 0:
            self.msg_timer -= dt
            m = self.font.render(self.msg, True, (255, 255, 180))
            self.screen.blit(m, ((WIDTH - m.get_width()) // 2, 40))

    def _overlaps_player(self, bx: int, by: int, bz: int) -> bool:
        assert self.player
        p = self.player
        return (
            p.x + PLAYER_W > bx
            and p.x - PLAYER_W < bx + 1
            and p.y + PLAYER_H > by
            and p.y < by + 1
            and p.z + PLAYER_W > bz
            and p.z - PLAYER_W < bz + 1
        )

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            # Cap huge stalls (alt-tab)
            dt = min(dt, 0.05)
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
            mouse_pos = pygame.mouse.get_pos()

            if self.state == STATE_MENU:
                self.run_menu(events, mouse_pos)
            elif self.state == STATE_OPTIONS:
                self.run_options(events, mouse_pos)
            elif self.state == STATE_PLAY:
                self.run_play(events, dt)

            pygame.display.flip()


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
