import unittest
from pathlib import Path

import torch
from PIL import Image
import numpy as np

from dhp.inference import predict_image
from dhp.losses import DepthHypothesisLoss
from dhp.model import DepthHypothesisPackLite


class DepthHypothesisPackModelTest(unittest.TestCase):
    def test_output_contract_and_order(self):
        model = DepthHypothesisPackLite(
            pretrained_encoder=False,
            freeze_encoder=True,
            decoder_channels=32,
        )
        output = model(torch.zeros(2, 3, 64, 96))
        self.assertEqual(output["depth"].shape, (2, 4, 64, 96))
        self.assertTrue(torch.all(output["depth"][:, 1:] > output["depth"][:, :-1]))
        self.assertTrue(
            torch.all(
                output["presence_probability"][:, 1:]
                <= output["presence_probability"][:, :-1]
            )
        )
        self.assertTrue(torch.all(output["uncertainty"] > 0))

    def test_loss_is_finite_and_has_gradient(self):
        model = DepthHypothesisPackLite(
            pretrained_encoder=False,
            freeze_encoder=True,
            decoder_channels=32,
        )
        image = torch.randn(1, 3, 64, 64)
        output = model(image)
        target = torch.stack(
            [
                torch.full((64, 64), 1.0),
                torch.full((64, 64), 1.2),
                torch.zeros((64, 64)),
                torch.zeros((64, 64)),
            ]
        )[None]
        loss = DepthHypothesisLoss()(output, target, target > 0)
        self.assertTrue(torch.isfinite(loss["total"]))
        self.assertEqual(loss["order_violation"].item(), 0.0)
        loss["total"].backward()
        self.assertIsNotNone(model.output[-1].weight.grad)

    def test_presence_loss_keeps_sparse_deep_layer_gradient(self):
        criterion = DepthHypothesisLoss()
        gate_logits = torch.zeros(1, 4, 2, 2, requires_grad=True)
        prediction = {
            "depth": torch.ones(1, 4, 2, 2),
            "presence_probability": torch.cumprod(
                torch.sigmoid(gate_logits), dim=1
            ),
            "presence_logits": gate_logits,
            "uncertainty": torch.full((1, 4, 2, 2), 0.1),
        }
        valid = torch.zeros(1, 4, 2, 2, dtype=torch.bool)
        valid[:, 0] = True
        valid[:, 1, 0, 0] = True
        loss = criterion(prediction, torch.ones(1, 4, 2, 2), valid)["total"]
        loss.backward()
        self.assertGreater(float(gate_logits.grad[:, 1, 0, 0].abs()), 0.0)

    def test_full_image_inference_restores_original_shape(self):
        model = DepthHypothesisPackLite(
            pretrained_encoder=False,
            freeze_encoder=True,
            decoder_channels=32,
        ).eval()
        image = Image.fromarray(np.zeros((45, 80, 3), dtype=np.uint8))
        output = predict_image(model, image, torch.device("cpu"), input_height=64)
        self.assertEqual(output["depth"].shape, (4, 45, 80))
        self.assertEqual(output["presence_probability"].shape, (4, 45, 80))

    def test_dinov2_small_encoder_preserves_output_contract(self):
        model = DepthHypothesisPackLite(
            encoder_name="dinov2_small",
            pretrained_encoder=False,
            freeze_encoder=True,
            decoder_channels=8,
        ).eval()
        with torch.inference_mode():
            output = model(torch.zeros(1, 3, 31, 45))
        self.assertEqual(output["depth"].shape, (1, 4, 31, 45))
        self.assertTrue(torch.all(output["depth"][:, 1:] > output["depth"][:, :-1]))
        self.assertTrue(all(not parameter.requires_grad for parameter in model.encoder.parameters()))
        self.assertEqual(model.method_name, "DepthHypothesisPackDINOv2S_v1")

    def test_dinov2_partial_tuning_only_unfreezes_last_blocks(self):
        model = DepthHypothesisPackLite(
            encoder_name="dinov2_small",
            pretrained_encoder=False,
            freeze_encoder=True,
            trainable_encoder_blocks=1,
            decoder_channels=8,
        )
        layers = model.encoder.network.encoder.layer
        self.assertTrue(all(not p.requires_grad for p in layers[-2].parameters()))
        self.assertTrue(all(p.requires_grad for p in layers[-1].parameters()))
        self.assertTrue(
            all(p.requires_grad for p in model.encoder.network.layernorm.parameters())
        )
        self.assertEqual(model.method_name, "DepthHypothesisPackDINOv2SFT1_v1")

    def test_depth_anything_v2_small_preserves_output_contract(self):
        model = DepthHypothesisPackLite(
            encoder_name="depth_anything_v2_small",
            pretrained_encoder=False,
            freeze_encoder=True,
            decoder_channels=8,
            encoder_source_root=(
                Path(__file__).resolve().parents[2]
                / "external"
                / "remake"
                / "official"
                / "relat_depth_models"
            ),
        ).eval()
        with torch.inference_mode():
            output = model(torch.zeros(1, 3, 31, 45))
        self.assertEqual(output["depth"].shape, (1, 4, 31, 45))
        self.assertTrue(torch.all(output["depth"][:, 1:] > output["depth"][:, :-1]))
        self.assertTrue(all(not parameter.requires_grad for parameter in model.encoder.parameters()))
        self.assertEqual(model.method_name, "DepthHypothesisPackDAV2S_v1")


if __name__ == "__main__":
    unittest.main()
