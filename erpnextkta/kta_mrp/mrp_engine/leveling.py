"""Kapasite Dengeleme ve Ramp-up (Smoothing) Algoritmaları (Saf Fonksiyonlar)."""

from collections import defaultdict


def distribute_proportional(total_qty: int, weights: dict) -> dict:
    """Largest Remainder Method (Hare-Niemeyer) ile kesin tam sayı orantısal dağıtım.

    Dağıtılan toplam miktar, her zaman tam olarak total_qty'ye eşit olur.
    """
    total_weight = sum(weights.values())
    if total_weight <= 0 or total_qty <= 0:
        return {k: 0 for k in weights}

    raw = {k: total_qty * (w / total_weight) for k, w in weights.items()}
    floored = {k: int(v) for k, v in raw.items()}
    remainders = {k: raw[k] - floored[k] for k in raw}
    diff = total_qty - sum(floored.values())

    # Kalanları en büyükten küçüğe doğru paylaştır
    for k in sorted(remainders, key=remainders.get, reverse=True):
        if diff <= 0:
            break
        floored[k] += 1
        diff -= 1

    return floored


def forward_scheduling(
    valid_weeks: list,
    group_items: dict,
    group_capacity: dict,
    item_backlog: dict,
    item_week_demand: dict,
    item_backlog_kanban: dict = None,
    item_week_kanban: dict = None,
    item_backlog_wo: dict = None,
    item_week_wo: dict = None,
    leveling_enabled: bool = True,
):
    """PASS 1: İleriye Yönlü Kapasite Dengeleme (Forward Scheduling).

    Kapasiteyi aşan geçmiş backlog ve haftalık talepleri sonraki haftalara devreder (carry-over).
    Dengeleme kapalıysa doğrudan talep miktarlarını plana yazar.
    """
    item_backlog_kanban = item_backlog_kanban or defaultdict(int)
    item_week_kanban = item_week_kanban or defaultdict(lambda: defaultdict(int))
    item_backlog_wo = item_backlog_wo or defaultdict(int)
    item_week_wo = item_week_wo or defaultdict(lambda: defaultdict(int))

    item_final_plan = defaultdict(lambda: defaultdict(int))
    item_final_kanban_plan = defaultdict(lambda: defaultdict(int))
    item_final_wo_plan = defaultdict(lambda: defaultdict(int))

    item_carry_over = item_backlog.copy()
    item_carry_over_kanban = item_backlog_kanban.copy()
    item_carry_over_wo = item_backlog_wo.copy()

    for week in valid_weeks:
        for group, items_in_group in group_items.items():
            cap = group_capacity.get(group, 0)

            if leveling_enabled:
                remaining_cap = cap

                # 1. Backlog dağıtımı (öncelikli)
                total_item_backlogs = {
                    i: item_carry_over[i]
                    for i in items_in_group
                    if item_carry_over[i] > 0
                }
                sum_backlog = sum(total_item_backlogs.values())

                if sum_backlog > 0 and remaining_cap > 0:
                    backlog_to_produce = min(sum_backlog, remaining_cap)
                    shares = distribute_proportional(
                        backlog_to_produce, total_item_backlogs
                    )

                    for i, share in shares.items():
                        k_ratio = 0
                        w_ratio = 0
                        if share > 0 and item_carry_over[i] > 0:
                            k_ratio = item_carry_over_kanban[i] / item_carry_over[i]
                            w_ratio = item_carry_over_wo[i] / item_carry_over[i]
                        k_share = round(share * k_ratio)
                        w_share = round(share * w_ratio)

                        item_final_plan[i][week] += share
                        item_carry_over[i] -= share

                        item_final_kanban_plan[i][week] += k_share
                        item_carry_over_kanban[i] -= k_share

                        item_final_wo_plan[i][week] += w_share
                        item_carry_over_wo[i] -= w_share

                        remaining_cap -= share

                # 2. Mevcut hafta talebi dağıtımı
                total_item_current = {
                    i: item_week_demand[i].get(week, 0)
                    for i in items_in_group
                    if item_week_demand[i].get(week, 0) > 0
                }
                sum_current = sum(total_item_current.values())

                if sum_current > 0:
                    if remaining_cap > 0:
                        current_to_produce = min(sum_current, remaining_cap)
                        shares = distribute_proportional(
                            current_to_produce, total_item_current
                        )

                        for i, share in shares.items():
                            k_ratio = 0
                            w_ratio = 0
                            if share > 0 and total_item_current[i] > 0:
                                k_ratio = (
                                    item_week_kanban[i].get(week, 0)
                                    / total_item_current[i]
                                )
                                w_ratio = (
                                    item_week_wo[i].get(week, 0) / total_item_current[i]
                                )
                            k_share = round(share * k_ratio)
                            w_share = round(share * w_ratio)

                            item_final_plan[i][week] += share
                            item_carry_over[i] += total_item_current[i] - share

                            item_final_kanban_plan[i][week] += k_share
                            item_carry_over_kanban[i] += (
                                item_week_kanban[i].get(week, 0) - k_share
                            )

                            item_final_wo_plan[i][week] += w_share
                            item_carry_over_wo[i] += (
                                item_week_wo[i].get(week, 0) - w_share
                            )
                    else:
                        for i in items_in_group:
                            item_carry_over[i] += item_week_demand[i].get(week, 0)
                            item_carry_over_kanban[i] += item_week_kanban[i].get(
                                week, 0
                            )
                            item_carry_over_wo[i] += item_week_wo[i].get(week, 0)
            else:
                for i in items_in_group:
                    val = item_carry_over[i] + item_week_demand[i].get(week, 0)
                    k_val = item_carry_over_kanban[i] + item_week_kanban[i].get(week, 0)
                    w_val = item_carry_over_wo[i] + item_week_wo[i].get(week, 0)
                    if week != valid_weeks[0]:
                        val = item_week_demand[i].get(week, 0)
                        k_val = item_week_kanban[i].get(week, 0)
                        w_val = item_week_wo[i].get(week, 0)
                    item_final_plan[i][week] = val
                    item_final_kanban_plan[i][week] = k_val
                    item_final_wo_plan[i][week] = w_val

    return item_final_plan, item_final_kanban_plan, item_final_wo_plan


def backward_rampup_smoothing(
    valid_weeks: list,
    group_items: dict,
    group_capacity: dict,
    item_final_plan: dict,
    item_final_kanban_plan: dict,
    item_final_wo_plan: dict,
    ramp_weeks: int = 3,
    trigger_ratio: float = 0.70,
    max_capacity_ratio: float = 0.95,
    min_smoothing_qty: int = 10,
):
    """PASS 2 & 3: Geriye Doğru Düzeltme ve Ramp-up (Multi-Pass Smoothing).

    Ani talep sıçramalarını ve testere dişi dalgalanmalarını geriye doğru (boş önceki haftalara) yayar.
    """
    if ramp_weeks <= 0 or not valid_weeks:
        return

    for group, cap in group_capacity.items():
        if cap <= 0:
            continue
        items = group_items.get(group, [])
        if not items:
            continue

        for _ in range(ramp_weeks):
            for w in reversed(range(1, len(valid_weeks))):
                curr_w = valid_weeks[w]
                prev_w = valid_weeks[w - 1]

                curr_load = sum(item_final_plan[it].get(curr_w, 0) for it in items)
                prev_load = sum(item_final_plan[it].get(prev_w, 0) for it in items)

                move_qty = 0

                # Sadece yüksek doluluk varsa veya yayılma devam ediyorsa yumuşat
                if curr_load > cap * trigger_ratio or prev_load > cap * trigger_ratio:
                    if curr_load > prev_load:
                        avg = (curr_load + prev_load) / 2
                        move_qty = curr_load - avg

                        # Önceki haftanın kapasitesini taşırma (maks tavan)
                        if prev_load + move_qty > cap * max_capacity_ratio:
                            move_qty = max(0, (cap * max_capacity_ratio) - prev_load)

                if move_qty > min_smoothing_qty:
                    curr_item_loads = {
                        it: item_final_plan[it].get(curr_w, 0)
                        for it in items
                        if item_final_plan[it].get(curr_w, 0) > 0
                    }
                    shares = distribute_proportional(int(move_qty), curr_item_loads)

                    for it, share in shares.items():
                        if share <= 0:
                            continue

                        k_ratio = 0
                        w_ratio = 0
                        if item_final_plan[it].get(curr_w, 0) > 0:
                            k_ratio = item_final_kanban_plan[it].get(
                                curr_w, 0
                            ) / item_final_plan[it].get(curr_w, 0)
                            w_ratio = item_final_wo_plan[it].get(
                                curr_w, 0
                            ) / item_final_plan[it].get(curr_w, 0)
                        k_share = round(share * k_ratio)
                        w_share = round(share * w_ratio)

                        item_final_plan[it][curr_w] -= share
                        item_final_plan[it][prev_w] += share

                        item_final_kanban_plan[it][curr_w] -= k_share
                        item_final_kanban_plan[it][prev_w] += k_share

                        item_final_wo_plan[it][curr_w] -= w_share
                        item_final_wo_plan[it][prev_w] += w_share
