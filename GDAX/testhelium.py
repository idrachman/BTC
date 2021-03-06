from helium import Helium
from book import Book, Order

import unittest
import pytest

from testbook import DummyBlobProtocol
from teststrategy import DummyRESTProtocol


testparams = {"debug"            : False,
              "dump_on_lockdown" : True,
              "max_distance"     : 2.00,
              "spread"           : 0.10,
              "trade_size"       : 1.0,
              "shading"          : 0.5}

class DemoHelium(Helium):
    def __init__(self):
        Helium.__init__(self, DummyRESTProtocol(), testparams)

    def on_place(self, oid, side, price, size, otype):
        Helium.on_place(self, oid, side, price, size, otype)
        if otype == "limit":
            self.book.add(oid, side, price, size)

class DemoBook(Book):
    def __init__(self):
        Book.__init__(self, DummyBlobProtocol())
        # Create following book.
        '''
        Z1 1.0 - 100.00 | 100.10 - 1.0 Z3
        Z2 1.0 -  99.50 | 101.00 - 1.0  Z4
        '''
        self.add("Z1", "buy",  100.00, 1.0)
        self.add("Z2", "buy",   99.50, 1.0)
        self.add("Z3", "sell", 100.10, 1.0)
        self.add("Z4", "sell", 101.00, 1.0)

class MyTest(unittest.TestCase):
    def test_update_bids(self):
        book = DemoBook()
        strat = DemoHelium()
        book.add_client(strat)

        # Update the size of order Z4 to trigger update().
        book.change("Z4", "sell", 1.0)
        assert strat.open_orders == {"B1": Order("B1", "buy", 100.00, 1.0)}

    def test_on_partial_fill(self):
        book = DemoBook()
        strat = DemoHelium()
        book.add_client(strat)

        # Update the size of order Z4 to trigger update().
        book.change("Z4", "sell", 1.0)
        assert strat.open_orders == {"B1": Order("B1", "buy", 100.00, 1.0)}

        # Hit 1.5 of the bids at $100, 1.0 of the original order and 0.5 of the strategy's bid.
        book.match("Z1", "buy", 100.00, 1.0)
        book.match("B1", "buy", 100.00, 0.5)

        # Check that the ask was placed.
        assert strat.open_orders == {"A1": Order("A1", "sell", 100.10, 0.5), "B1": Order("B1", "buy", 100.00, 0.5)}

    def test_on_complete_fill(self):
        book = DemoBook()
        strat = DemoHelium()
        book.add_client(strat)

        # Update the size of order Z4 to trigger update().
        book.change("Z4", "sell", 1.0)
        assert strat.open_orders == {"B1": Order("B1", "buy", 100.00, 1.0)}

        # Hit 2.0 of the bids at $100, 1.0 of the original order and 1.0 of the strategy's bid.
        book.match("Z1", "buy", 100.00, 1.0)
        book.match("B1", "buy", 100.00, 1.0)
        assert strat.open_orders == {"A1": Order("A1", "sell", 100.10, 1.0)}

    def test_lockdown_max_distance(self):
        book = DemoBook()
        strat = DemoHelium()
        book.add_client(strat)

        # Update the book to trigger update().
        book.change("Z4", "sell", 1.0)
        assert strat.open_orders["B1"] == Order("B1", "buy", 100.00, 1.0)

        # Match the bid so the strat places an ask.
        book.match("Z1", "buy", 100.00, 1.0)
        book.match("B1", "buy", 100.00, 1.0)
        assert strat.open_orders["A1"] == Order("A1", "sell", 100.10, 1.0)

        # Change midpoint to 20.50.
        # When the strat checks the distance it should lockdown.
        '''
        Z5 1.0 - 20.00 | 21.00 - 1.0 Z6
        '''
        book.add("Z5", "buy", 20.0, 1.0)
        book.add("Z6", "sell", 21.0, 1.0)
        book.done("Z2")
        book.done("Z3")
        book.done("Z4")
        assert strat.enabled == False
        assert strat.lockdown_reason == "max distance exceeded"

    def test_lockdown_stop_loss(self):
        book = DemoBook()
        editedparams = testparams.copy()
        editedparams["stop_loss"] = 0.30
        strat = Helium(DummyRESTProtocol(), editedparams)
        book.add_client(strat)

        # Update the book to trigger update().
        book.change("Z4", "sell", 1.0)

        # Lose 1 BTC.
        strat.btc_position = -1.0

        # Update the book to trigger update().
        book.change("Z4", "sell", 0.5)

        assert strat.enabled == False
        assert strat.lockdown_reason == "stop loss of 0.30 triggered"
