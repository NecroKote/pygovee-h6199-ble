from govee_h6199_ble import Capabilities, ChipFamily, DeviceInfo, Version
from govee_h6199_ble.model import Pact


def info(soft, hard, wifi_soft=None, wifi_hard=None, pact=None):
    v = lambda s: Version.parse(s) if s else None
    return DeviceInfo(v(soft), v(hard), v(wifi_soft), v(wifi_hard), pact)


def test_version_compares_numerically():
    assert Version.parse("1.10.04") > Version.parse("1.9.11")
    assert str(Version.parse("1.9.1")) == "1.09.01"


def test_reference_device_with_segment_brightness():
    caps = Capabilities.from_info(info("1.10.04", "3.02.01", "1.00.30", "1.03.00"))
    assert caps.chip is ChipFamily.FRK
    assert caps.video_segment_brightness
    assert not caps.video_brightness  # replaced by segment brightness
    assert caps.white_balance and caps.service_scenes and caps.ai_effects


def test_reference_device_wifi_unknown():
    caps = Capabilities.from_info(info("1.10.04", "3.02.01"))
    assert not caps.video_segment_brightness
    assert not caps.white_balance
    assert caps.service_scenes


def test_frk_newer_whole_screen_brightness():
    caps = Capabilities.from_info(info("1.10.04", "3.03.01", "1.00.29", "1.03.00"))
    assert caps.video_brightness
    assert not caps.video_segment_brightness


def test_frk_ai_variant_needs_pact_for_scenes():
    assert not Capabilities.from_info(info("1.10.04", "3.04.01")).service_scenes
    caps = Capabilities.from_info(info("1.10.04", "3.04.01", pact=Pact(3, 1)))
    assert caps.service_scenes
    # AI effects follow the soft-version rule, not the pact
    assert caps.ai_effects
    assert not Capabilities.from_info(info("1.07.01", "3.04.01", pact=Pact(3, 1))).ai_effects
    assert Capabilities.from_info(info("1.07.01", "3.04.01", pact=Pact(4, 1))).ai_effects


def test_telink_video_brightness_pact_v1_only():
    args = ("1.07.01", "1.02.00", "1.00.28", "1.00.01")
    assert Capabilities.from_info(info(*args, pact=Pact(1, 1))).video_brightness
    assert not Capabilities.from_info(info(*args, pact=Pact(2, 1))).video_brightness


def test_zone_brightness_needs_v2():
    assert not Capabilities.from_info(info("1.10.04", "3.02.01", pact=Pact(1, 1))).zone_brightness
    assert Capabilities.from_info(info("1.10.04", "3.02.01", pact=Pact(2, 1))).zone_brightness
    assert Capabilities.from_info(info("1.10.04", "3.02.01")).zone_brightness


def test_unknown_chip_gets_nothing():
    caps = Capabilities.from_info(info("9.99.99", "2.01.00"))
    assert caps.chip is ChipFamily.BK
    assert not (caps.service_scenes or caps.white_balance or caps.video_brightness)
