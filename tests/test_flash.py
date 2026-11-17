#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""Regression tests for stream flashes and the Flash separator."""

from unittest import TestCase, TestSuite

from lib.corriente import Corriente
from equipment.distillation import Flash


class TestFlash(TestCase):
    """Test zero-quality streams, flash helpers and Flash specifications"""

    def setUp(self):
        self.feed = Corriente(
            T=300, P=5e5, ids=[62], fraccionMolar=[1.], caudalMasico=1.)

    def test_zero_quality_is_calculable(self):
        stream = Corriente(
            P=5e5, x=0, ids=[62], fraccionMolar=[1.], caudalMasico=1.)
        self.assertEqual(stream.status, 1)
        self.assertAlmostEqual(float(stream.x), 0)

        clone = self.feed.clone(P=5e5, x=0)
        self.assertEqual(clone.status, 1)
        self.assertAlmostEqual(float(clone.x), 0)

    def test_zero_flow(self):
        stream = self.feed.zeroFlow()
        self.assertEqual(stream.status, 1)
        self.assertEqual(float(stream.caudalmasico), 0)
        self.assertEqual(float(stream.caudalmolar), 0)
        self.assertEqual(float(stream.h), 0)

    def test_flash_pt(self):
        stream = self.feed.flash(P=5e5, T=400)
        self.assertEqual(stream.status, 1)
        self.assertAlmostEqual(float(stream.T), 400)
        self.assertGreater(float(stream.h), float(self.feed.h))

    def test_flash_px(self):
        stream = self.feed.flash(P=5e5, x=0.5)
        self.assertEqual(stream.status, 1)
        self.assertAlmostEqual(float(stream.x), 0.5)
        liquid = self.feed.flash(P=5e5, x=0)
        vapor = self.feed.flash(P=5e5, x=1)
        self.assertAlmostEqual(
            float(stream.h), (float(liquid.h)+float(vapor.h))/2)

    def test_flash_duty(self):
        stream = self.feed.flash(P=5e5, Q=1e6)
        self.assertEqual(stream.status, 1)
        self.assertAlmostEqual(float(stream.h)-float(self.feed.h), 1e6)

    def test_flash_adiabatic(self):
        stream = self.feed.flash(P=2e3, adiabatic=True)
        self.assertEqual(stream.status, 1)
        self.assertAlmostEqual(float(stream.h), float(self.feed.h))
        self.assertGreater(float(stream.x), 0)
        self.assertLess(float(stream.x), 1)

    def test_separator_vapor_fraction(self):
        flash = Flash(entrada=self.feed, flash=2, Pout=5e5, xout=0.5)
        self.assertEqual(flash.status, 1)
        self.assertAlmostEqual(float(flash.VaporMassFlow), 0.5)
        self.assertAlmostEqual(float(flash.LiquidMassFlow), 0.5)
        self.assertAlmostEqual(float(flash.salida[0].x), 1)
        self.assertAlmostEqual(float(flash.salida[1].x), 0)
        self.assertAlmostEqual(
            float(flash.Q),
            float(flash.salida[0].h)+float(flash.salida[1].h)
            - float(self.feed.h))

    def test_separator_all_liquid(self):
        flash = Flash(entrada=self.feed, flash=0)
        self.assertEqual(flash.status, 1)
        self.assertAlmostEqual(float(flash.VaporMassFlow), 0)
        self.assertAlmostEqual(float(flash.LiquidMassFlow), 1)
        self.assertAlmostEqual(float(flash.Tout), 300)
        self.assertAlmostEqual(float(flash.Q), 0)

    def test_separator_zero_vapor_fraction(self):
        flash = Flash(entrada=self.feed, flash=2, Pout=5e5, xout=0)
        self.assertEqual(flash.status, 1)
        self.assertAlmostEqual(float(flash.VaporMassFlow), 0)
        self.assertAlmostEqual(float(flash.LiquidMassFlow), 1)
        self.assertAlmostEqual(float(flash.salida[1].x), 0)

    def test_separator_outlet_temperature(self):
        flash = Flash(entrada=self.feed, flash=1, Pout=5e5, Tout=400)
        self.assertEqual(flash.status, 1)
        self.assertAlmostEqual(float(flash.Tout), 400)
        self.assertAlmostEqual(float(flash.LiquidMassFlow), 1)

    def test_separator_heat_duty(self):
        flash = Flash(entrada=self.feed, flash=3, Pout=5e5, Q=1e6)
        self.assertEqual(flash.status, 1)
        self.assertAlmostEqual(float(flash.Q), 1e6)
        self.assertAlmostEqual(
            float(flash.salida[0].h)+float(flash.salida[1].h),
            float(self.feed.h)+1e6)

    def test_separator_adiabatic(self):
        flash = Flash(entrada=self.feed, flash=4, DeltaP=498000)
        self.assertEqual(flash.status, 1)
        self.assertAlmostEqual(float(flash.Pout), 2000)
        self.assertAlmostEqual(float(flash.Q), 0)
        self.assertGreater(float(flash.salida[0].x), 0)

    def test_separator_vapor_fraction_is_not_adiabatic(self):
        flash = Flash(entrada=self.feed, flash=2, Pout=2.5e5, xout=0.5)
        self.assertEqual(flash.status, 1)
        self.assertAlmostEqual(float(flash.Tout), 400.56, delta=0.2)
        self.assertGreater(float(flash.Q), 0)
        adiabatic = Flash(entrada=self.feed, flash=4, Pout=2.5e5)
        self.assertEqual(adiabatic.status, 1)
        self.assertAlmostEqual(float(adiabatic.Q), 0)
        self.assertLess(float(adiabatic.Tout), float(self.feed.T)+1)


def load_tests(loader, tests, ignore):
    suite = TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestFlash))
    return suite
