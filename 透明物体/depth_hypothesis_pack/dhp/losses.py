"""Losses for ordered metric-depth hypotheses."""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class DepthHypothesisLoss(nn.Module):
    def __init__(
        self,
        presence_weight: float = 0.25,
        front_weight: float = 0.20,
        uncertainty_weight: float = 0.05,
        maximum_presence_pos_weight: float = 20.0,
    ) -> None:
        super().__init__()
        self.presence_weight = float(presence_weight)
        self.front_weight = float(front_weight)
        self.uncertainty_weight = float(uncertainty_weight)
        self.maximum_presence_pos_weight = float(maximum_presence_pos_weight)

    def _presence_loss(
        self,
        gate_logits: torch.Tensor,
        target_valid: torch.Tensor,
    ) -> torch.Tensor:
        """Balance conditional layer-presence gates within eligible rays."""

        eligible = torch.cat(
            [torch.ones_like(target_valid[:, :1]), target_valid[:, :-1]], dim=1
        ).bool()
        layer_losses = []
        for layer in range(gate_logits.shape[1]):
            layer_eligible = eligible[:, layer]
            if not torch.any(layer_eligible):
                continue
            logits = gate_logits[:, layer][layer_eligible]
            target = target_valid[:, layer][layer_eligible].float()
            positives = target.sum()
            negatives = target.numel() - positives
            positive_weight = (
                (negatives / positives).clamp(
                    min=0.25, max=self.maximum_presence_pos_weight
                )
                if positives.item() > 0
                else target.new_tensor(1.0)
            )
            layer_losses.append(
                F.binary_cross_entropy_with_logits(
                    logits,
                    target,
                    pos_weight=positive_weight.detach(),
                )
            )
        if not layer_losses:
            return gate_logits.new_zeros(())
        return torch.stack(layer_losses).mean()

    def forward(
        self,
        prediction: dict[str, torch.Tensor],
        target_depth: torch.Tensor,
        target_valid: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        predicted_depth = prediction["depth"]
        presence = prediction["presence_probability"]
        presence_logits = prediction["presence_logits"]
        uncertainty = prediction["uncertainty"]
        if predicted_depth.shape != target_depth.shape:
            raise ValueError(
                f"Prediction {predicted_depth.shape} does not match target {target_depth.shape}"
            )
        target_valid = target_valid.bool()
        valid_float = target_valid.float()
        valid_count = valid_float.sum().clamp_min(1.0)

        depth_error = F.smooth_l1_loss(
            predicted_depth,
            target_depth,
            reduction="none",
            beta=0.05,
        )
        depth_loss = (depth_error * valid_float).sum() / valid_count

        front_valid = valid_float[:, :1]
        front_count = front_valid.sum().clamp_min(1.0)
        front_loss = (depth_error[:, :1] * front_valid).sum() / front_count

        if presence.shape != presence_logits.shape:
            raise ValueError("Presence probabilities and gate logits must have one shape")
        presence_loss = self._presence_loss(presence_logits, target_valid)

        absolute_error = torch.abs(predicted_depth - target_depth)
        laplace_nll = absolute_error / uncertainty + torch.log(2.0 * uncertainty)
        uncertainty_loss = (laplace_nll * valid_float).sum() / valid_count

        if predicted_depth.shape[1] > 1:
            order_violation = F.relu(
                predicted_depth[:, :-1] - predicted_depth[:, 1:]
            ).max()
        else:
            order_violation = predicted_depth.new_zeros(())

        total = (
            depth_loss
            + self.front_weight * front_loss
            + self.presence_weight * presence_loss
            + self.uncertainty_weight * uncertainty_loss
        )
        return {
            "total": total,
            "depth": depth_loss,
            "front": front_loss,
            "presence": presence_loss,
            "uncertainty": uncertainty_loss,
            "order_violation": order_violation,
        }
