from __future__ import annotations

import csv
import math
from datetime import date
from pathlib import Path

from manim import *

from rvcadence import (
    build_allowed_offsets,
    contiguous_ranges,
    evaluate_candidate,
    parse_obs_windows,
    best_candidate as rvcadence_best_candidate,
)
from rvcadence._phase import circ_dist_01


def phase_to_point(center: np.ndarray, radius: float, phase: float) -> np.ndarray:
    theta = TAU * phase
    return center + radius * np.array([math.cos(theta), math.sin(theta), 0.0])


def parse_optional_float(value: str) -> float:
    text = str(value).strip().lower()
    if text in {"", "nan", "n/a", "na", "none"}:
        return math.nan
    return float(text)


def load_target_row(table_path: Path, target_name: str) -> dict[str, str]:
    with table_path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        if (row.get("Planet") or "").strip() == target_name:
            return row
    raise ValueError(f"Target '{target_name}' not found in {table_path}")


class CadenceGreedyExplainer(Scene):
    def construct(self):
        table_path = Path(__file__).resolve().parents[2] / "ESPRESSO_large_program" / "planet_properties_table.csv"
        target_name = "HIP 113103 b"
        target = load_target_row(table_path, target_name)

        p_planet_d = float(target["P_d"])
        p_rot_d = parse_optional_float(target.get("Prot_lit_d", "nan"))
        n_obs = int(float(target["N_obs"]))

        season_start = date(2026, 5, 1)
        season_end = date(2027, 4, 30)
        baseline_days = (season_end - season_start).days
        min_gap_days = 1
        windows = parse_obs_windows(target.get("obs_windows_2026_2027", ""))
        allowed_offsets = build_allowed_offsets(season_start, season_end, windows)
        if len(allowed_offsets) < 2:
            raise ValueError(f"Target '{target_name}' has <2 allowed dates in obs_windows_2026_2027.")
        allowed_set = set(allowed_offsets)
        unavailable_offsets = [t for t in range(0, baseline_days + 1) if t not in allowed_set]
        iterations_to_show = min(10, max(0, n_obs - 2), max(0, len(allowed_offsets) - 2))

        left_center = np.array([-4.2, 0.78, 0.0])
        right_center = np.array([0.0, 0.78, 0.0])
        meter_center = np.array([4.2, 0.78, 0.0])
        radius = 1.30

        eq = MathTex(
            r"s(t)=",
            r"0.55",
            r"d_p",
            r"+",
            r"0.30",
            r"d_s",
            r"+",
            r"0.15",
            r"d_t",
            font_size=42,
            color=GRAY_A,
        ).to_edge(UP, buff=0.2)
        dp_term = eq[2]
        dr_term = eq[5]
        dt_term = eq[8]
        dp_term.set_color(BLUE_B)
        dr_term.set_color(GREEN_B)
        dt_term.set_color(YELLOW_B)

        planet_circle = Circle(radius=radius, color=BLUE_D, stroke_width=4).move_to(left_center)
        rot_circle = Circle(radius=radius, color=GREEN_D, stroke_width=4).move_to(right_center)
        planet_title = Text("Planet phase", font_size=26, color=BLUE_B).next_to(planet_circle, DOWN, buff=0.18)
        rot_title = Text("Stellar phase", font_size=26, color=GREEN_B).next_to(rot_circle, DOWN, buff=0.18)

        # "Clock hands" to indicate current candidate phase.
        planet_hand = Line(left_center, left_center + RIGHT * radius, color=BLUE_B, stroke_width=4)
        rot_hand = Line(right_center, right_center + RIGHT * radius, color=GREEN_B, stroke_width=4)

        timeline = NumberLine(
            x_range=[0, baseline_days, 50],
            length=12.2,
            include_numbers=False,
            include_ticks=False,
            label_direction=DOWN,
            font_size=18,
            color=GRAY_B,
        ).to_edge(DOWN, buff=1.05)
        month_ticks = VGroup()
        month_labels = VGroup()
        for month in range(5, 13):
            d = date(2026, month, 1)
            offset = (d - season_start).days
            x = timeline.n2p(offset)[0]
            tick = Line(np.array([x, timeline.get_y() - 0.10, 0.0]), np.array([x, timeline.get_y() + 0.10, 0.0]), color=GRAY_B, stroke_width=2)
            month_ticks.add(tick)
            month_labels.add(Text(d.strftime("%b"), font_size=18, color=GRAY_B).next_to(tick, DOWN, buff=0.12))
        for month in range(1, 5):
            d = date(2027, month, 1)
            offset = (d - season_start).days
            x = timeline.n2p(offset)[0]
            tick = Line(np.array([x, timeline.get_y() - 0.10, 0.0]), np.array([x, timeline.get_y() + 0.10, 0.0]), color=GRAY_B, stroke_width=2)
            month_ticks.add(tick)
            month_labels.add(Text(d.strftime("%b"), font_size=18, color=GRAY_B).next_to(tick, DOWN, buff=0.12))
        unavailable_lines = VGroup()
        for a, b in contiguous_ranges(unavailable_offsets):
            seg = Line(
                timeline.n2p(a),
                timeline.n2p(b),
                color=RED_E,
                stroke_width=9,
            )
            seg.set_z_index(1)
            unavailable_lines.add(seg)

        time_meter = RoundedRectangle(width=2.8, height=0.35, corner_radius=0.1, color=YELLOW_E, stroke_width=2)
        time_meter.move_to(meter_center)
        right_panel_title = Text("Time spacing", font_size=24, color=YELLOW_B)
        right_panel_title.move_to(np.array([meter_center[0], planet_title.get_y(), 0.0]))
        meter_fill = Rectangle(width=0.01, height=0.28, stroke_width=0, fill_color=YELLOW_D, fill_opacity=0.9)
        meter_fill.move_to(time_meter.get_left() + RIGHT * 0.005)
        meter_fill.set_z_index(3)
        target_label = Text(target_name, font_size=18, color=GRAY_C).set_opacity(0.65)
        target_label.to_corner(UL, buff=0.25)
        credit = Text("Credit: Pierrot Lamontagne & GPT", font_size=18, color=GRAY_C).set_opacity(0.65)
        credit.to_corner(DR, buff=0.25)

        self.play(
            FadeIn(eq, shift=UP * 0.1),
            Create(planet_circle),
            Create(rot_circle),
            Write(planet_title),
            Write(rot_title),
            Create(timeline),
            FadeIn(unavailable_lines),
            FadeIn(month_ticks),
            FadeIn(month_labels, lag_ratio=0.05),
            FadeIn(planet_hand),
            FadeIn(rot_hand),
            FadeIn(right_panel_title, shift=UP * 0.1),
            Create(time_meter),
            FadeIn(meter_fill),
            FadeIn(target_label),
            FadeIn(credit),
        )

        selected: list[int] = [allowed_offsets[0], allowed_offsets[-1]]
        planet_points = VGroup()
        rot_points = VGroup()
        time_points = VGroup()

        def add_selected_point(day: int, color: ManimColor = WHITE):
            p_phase = (day / p_planet_d) % 1.0
            r_phase = (day / p_rot_d) % 1.0
            p_dot = Dot(phase_to_point(left_center, radius, p_phase), radius=0.055, color=color)
            r_dot = Dot(phase_to_point(right_center, radius, r_phase), radius=0.055, color=color)
            t_dot = Dot(timeline.n2p(day), radius=0.06, color=color)
            planet_points.add(p_dot)
            rot_points.add(r_dot)
            time_points.add(t_dot)
            self.play(FadeIn(p_dot, scale=0.6), FadeIn(r_dot, scale=0.6), FadeIn(t_dot, scale=0.6), run_time=0.35)

        add_selected_point(allowed_offsets[0], color=GRAY_B)
        add_selected_point(allowed_offsets[-1], color=GRAY_B)
        self.wait(0.4)

        max_iter = iterations_to_show
        fast_forward_pause_s = 4.0

        def best_candidate_for_current_selection(current_selected: list[int]) -> "CandidateScore":
            return rvcadence_best_candidate(
                allowed_offsets, current_selected, p_planet_d, p_rot_d, baseline_days
            )

        def add_selected_point_fast(day: int):
            p_phase = (day / p_planet_d) % 1.0
            r_phase = (day / p_rot_d) % 1.0
            p_dot = Dot(phase_to_point(left_center, radius, p_phase), radius=0.055, color=RED_D).set_z_index(6)
            r_dot = Dot(phase_to_point(right_center, radius, r_phase), radius=0.055, color=RED_D).set_z_index(6)
            t_dot = Dot(timeline.n2p(day), radius=0.06, color=RED_D).set_z_index(6)
            self.play(FadeIn(p_dot, scale=0.6), FadeIn(r_dot, scale=0.6), FadeIn(t_dot, scale=0.6), run_time=0.06)
            self.play(
                p_dot.animate.set_color(WHITE),
                r_dot.animate.set_color(WHITE),
                t_dot.animate.set_color(WHITE),
                run_time=0.06,
            )
            planet_points.add(p_dot)
            rot_points.add(r_dot)
            time_points.add(t_dot)

        for k in range(max_iter):
            best = best_candidate_for_current_selection(selected)
            p_phase_best = (best.t / p_planet_d) % 1.0
            r_phase_best = (best.t / p_rot_d) % 1.0

            p_phases = [((x / p_planet_d) % 1.0) for x in selected]
            r_phases = [((x / p_rot_d) % 1.0) for x in selected]

            p_near = min(p_phases, key=lambda x: circ_dist_01(x, p_phase_best))
            r_near = min(r_phases, key=lambda x: circ_dist_01(x, r_phase_best))
            t_near = min(selected, key=lambda x: abs(x - best.t))

            p_angle = TAU * ((p_phase_best - p_near + 0.5) % 1.0 - 0.5)
            r_angle = TAU * ((r_phase_best - r_near + 0.5) % 1.0 - 0.5)

            p_arc = Arc(
                radius=radius * 1.04,
                start_angle=TAU * p_near,
                angle=p_angle,
                color=BLUE_C,
                stroke_width=6,
            ).move_arc_center_to(left_center)
            p_arc.set_z_index(2)
            r_arc = Arc(
                radius=radius * 1.04,
                start_angle=TAU * r_near,
                angle=r_angle,
                color=GREEN_C,
                stroke_width=6,
            ).move_arc_center_to(right_center)
            r_arc.set_z_index(2)

            t_line = Line(
                timeline.n2p(best.t),
                timeline.n2p(t_near),
                color=YELLOW_D,
                stroke_width=7,
            )
            t_line.set_z_index(2)

            best_time_dot = Dot(timeline.n2p(best.t), radius=0.075, color=RED_D)
            best_p_dot = Dot(phase_to_point(left_center, radius, p_phase_best), radius=0.07, color=RED_D)
            best_r_dot = Dot(phase_to_point(right_center, radius, r_phase_best), radius=0.07, color=RED_D)
            best_time_dot.set_z_index(6)
            best_p_dot.set_z_index(6)
            best_r_dot.set_z_index(6)
            pulse_t = Circle(radius=0.12, color=RED_D, stroke_width=3).move_to(best_time_dot).set_z_index(7)
            pulse_p = Circle(radius=0.11, color=RED_D, stroke_width=3).move_to(best_p_dot).set_z_index(7)
            pulse_r = Circle(radius=0.11, color=RED_D, stroke_width=3).move_to(best_r_dot).set_z_index(7)
            dt_frac = max(0.0, min(1.0, best.d_t))
            new_width = max(0.01, 2.76 * dt_frac)
            new_fill = Rectangle(
                width=new_width,
                height=0.28,
                stroke_width=0,
                fill_color=YELLOW_D,
                fill_opacity=0.9,
            )
            new_fill.move_to(time_meter.get_left() + RIGHT * (new_width / 2 + 0.02))
            new_fill.set_z_index(3)
            self.play(
                Rotate(
                    planet_hand,
                    angle=TAU * p_phase_best - planet_hand.get_angle(),
                    about_point=left_center,
                ),
                Rotate(
                    rot_hand,
                    angle=TAU * r_phase_best - rot_hand.get_angle(),
                    about_point=right_center,
                ),
                FadeIn(best_time_dot, scale=0.7),
                FadeIn(best_p_dot, scale=0.7),
                FadeIn(best_r_dot, scale=0.7),
                Create(pulse_t),
                Create(pulse_p),
                Create(pulse_r),
                Create(p_arc),
                Create(r_arc),
                Create(t_line),
                ReplacementTransform(meter_fill, new_fill),
                run_time=1.2,
            )
            meter_fill = new_fill
            p_link = Arrow(
                p_arc.point_from_proportion(0.5),
                dp_term.get_center(),
                buff=0.06,
                color=BLUE_C,
                stroke_width=3.2,
                max_tip_length_to_length_ratio=0.14,
            )
            r_link = Arrow(
                r_arc.point_from_proportion(0.5),
                dr_term.get_center(),
                buff=0.06,
                color=GREEN_C,
                stroke_width=3.2,
                max_tip_length_to_length_ratio=0.14,
            )
            t_link = Arrow(
                meter_fill.get_right(),
                dt_term.get_center(),
                buff=0.06,
                color=YELLOW_D,
                stroke_width=3.2,
                max_tip_length_to_length_ratio=0.14,
            )
            self.play(
                Create(p_link),
                Create(r_link),
                Create(t_link),
                Indicate(p_arc, color=BLUE_C, scale_factor=1.06),
                Indicate(r_arc, color=GREEN_C, scale_factor=1.06),
                Indicate(t_line, color=YELLOW_D, scale_factor=1.06),
                Indicate(meter_fill, color=YELLOW_D, scale_factor=1.06),
                Indicate(dp_term, color=BLUE_C, scale_factor=1.12),
                Indicate(dr_term, color=GREEN_C, scale_factor=1.12),
                Indicate(dt_term, color=YELLOW_D, scale_factor=1.12),
                run_time=0.75,
            )

            self.play(
                best_time_dot.animate.set_color(WHITE).scale(0.8),
                best_p_dot.animate.set_color(WHITE).scale(0.8),
                best_r_dot.animate.set_color(WHITE).scale(0.8),
                FadeOut(pulse_t, scale=1.8),
                FadeOut(pulse_p, scale=1.8),
                FadeOut(pulse_r, scale=1.8),
                FadeOut(p_arc),
                FadeOut(r_arc),
                FadeOut(t_line),
                FadeOut(p_link),
                FadeOut(r_link),
                FadeOut(t_link),
                run_time=0.35,
            )
            planet_points.add(best_p_dot)
            rot_points.add(best_r_dot)
            time_points.add(best_time_dot)
            selected.append(best.t)

        # Fast-forward through the remaining iterations to reach full N_obs coverage.
        while len(selected) < n_obs:
            best = best_candidate_for_current_selection(selected)
            add_selected_point_fast(best.t)
            selected.append(best.t)

        self.wait(fast_forward_pause_s)
