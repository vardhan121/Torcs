import unittest

from control import active_keys, pedal_levels, steering_from_wrists


class SteeringTests(unittest.TestCase):
    def test_horizontal_hands_mean_centered_wheel(self):
        self.assertAlmostEqual(steering_from_wrists([(0.2, 0.5), (0.8, 0.5)]), 0.0)

    def test_steering_is_bounded_at_extreme_angles(self):
        self.assertEqual(steering_from_wrists([(0.2, 0.9), (0.8, 0.1)]), -1.0)

    def test_one_hand_is_not_enough_to_steer(self):
        self.assertEqual(steering_from_wrists([(0.2, 0.5)]), 0.0)


class PedalTests(unittest.TestCase):
    def test_uncalibrated_or_missing_feet_are_safe(self):
        self.assertEqual(pedal_levels([(0.2, 0.4), (0.8, 0.4)], None), (0.0, 0.0))
        self.assertEqual(pedal_levels([(0.2, 0.4)], (0.5, 0.5)), (0.0, 0.0))

    def test_foot_lift_maps_to_pedal_pressure(self):
        left, right = pedal_levels([(0.2, 0.4), (0.8, 0.3)], (0.5, 0.5))
        self.assertAlmostEqual(left, 1.0)
        self.assertAlmostEqual(right, 1.0)

    def test_pedal_pressure_is_clamped(self):
        self.assertEqual(
            pedal_levels([(0.2, 0.0), (0.8, 0.5)], (0.5, 0.5)),
            (1.0, 0.0),
        )


class KeyMappingTests(unittest.TestCase):
    def test_centered_controls_send_no_keys(self):
        self.assertEqual(active_keys(0.0, 0.0, 0.0), frozenset())

    def test_steering_and_acceleration_map_to_torcs_arrows(self):
        self.assertEqual(active_keys(0.8, 0.8, 0.0), frozenset({"right", "up"}))

    def test_brake_takes_priority_over_accelerator(self):
        self.assertEqual(active_keys(0.0, 1.0, 0.8), frozenset({"down"}))


if __name__ == "__main__":
    unittest.main()
