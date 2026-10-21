import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from dftrader.analysis import analyze, hourly, validate_config
from dftrader.backtest import evaluate
from dftrader.collector import Collector, SourceError, integer, parse_detail, parse_listing
from dftrader.common import iso, read_json, write_json
from dftrader.notify import notify, select_alerts
from dftrader.pipeline import run, save_history, load_history

NOW = datetime(2026, 10, 21, 9, 30, tzinfo=timezone.utc)
AT = iso(NOW - timedelta(minutes=30))
CONFIG = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())


def listing(price='1.200', stock='2.500 đang rao', total=1, page_links=''):
    return f'<time datetime="{AT}">Cập nhật · {total} vật phẩm.</time><a class="au-card-link" href="/cho-dau-gia/123"><span class="au-name">Đạn A</span><span class="au-price">{price}</span><span class="au-stock">{stock}</span></a>{page_links}'


def item(price=800):
    return {'id': '123', 'name': 'Đạn A', 'url': 'https://dfloadout.gg/cho-dau-gia/123', 'at': AT, 'price': price, 'listed': 100}


def history():
    return [{'id':'123','at':iso(NOW - timedelta(minutes=30, hours=h)), 'price':1000 if h else 800,'listed':100} for h in range(168, -1, -1)]


def fee_config():
    config = copy.deepcopy(CONFIG)
    config['fee'] = {'confirmed': True, 'sale_rate': .05, 'listing_rate': .02, 'fixed_per_unit': 3}
    return config


class ParsingTests(unittest.TestCase):
    def test_vietnamese_separators(self):
        self.assertEqual(integer('1.934.401 đang rao'), 1934401)
        self.assertEqual(integer('1,200'), 1200)
        for bad in ['-100', '1.2', '12 abc', 'NaN', '']:
            with self.assertRaises(SourceError): integer(bad)

    def test_listing_identity_count_timestamp(self):
        items, total, pages, at = parse_listing(listing(page_links='<a href="?category=5&page=3">3</a>'))
        self.assertEqual((items[0]['price'], items[0]['listed'], total, pages, at), (1200,2500,1,3,AT))

    def test_unavailable_not_zero_price(self):
        items, *_ = parse_listing(listing('Chưa có người bán', 'Hết hàng'))
        self.assertIsNone(items[0]['price'])
        self.assertEqual(items[0]['listed'], 0)

    def test_changed_structure_rejected(self):
        with self.assertRaises(SourceError): parse_listing('<html>Maintenance</html>')

    def test_history_timezone_and_consistency(self):
        html = f'<h1 class="ai-title">Đạn A</h1><time datetime="{AT}"></time><span class="ai-price">800</span><table><tbody><tr><td>16:00 21/10/26</td><td>800</td><td>100</td></tr></tbody></table>'
        points = parse_detail(html, item())
        self.assertEqual(points[0]['at'], '2026-10-21T09:00:00Z')
        with self.assertRaises(SourceError): parse_detail(html.replace('>800<', '>900<'), item())

    def test_pagination_dedup(self):
        collector = Collector(CONFIG['collection'])
        with patch.object(collector, 'get', return_value=listing(total=2, page_links='<a href="?category=5&page=2">2</a>')):
            with self.assertRaisesRegex(SourceError, 'duplicate'): collector.collect()


class AnalysisTests(unittest.TestCase):
    def test_unknown_fee_disables_profit(self):
        result = analyze(item(), history(), CONFIG)
        self.assertEqual(result['status'], 'watch')
        self.assertIsNone(result['net_margin_pct'])
        self.assertIsNone(result['breakeven'])

    def test_known_fee_profit_math(self):
        result = analyze(item(), history(), fee_config())
        self.assertEqual(result['status'], 'opportunity')
        self.assertEqual(result['breakeven'], 864)
        self.assertEqual(result['target'], 1000)
        self.assertEqual(result['net_margin_pct'], 15.88)

    def test_future_never_changes_signal(self):
        a = analyze(item(), history(), fee_config())
        b = analyze(item(), history() + [{'id':'123','at':iso(NOW + timedelta(hours=4)),'price':999999,'listed':1}], fee_config())
        self.assertEqual(a, b)

    def test_hourly_weighting(self):
        raw = history()
        duplicate = {**raw[-1], 'at': '2026-10-21T09:00:10Z'}
        self.assertEqual(len(hourly(raw + [duplicate], NOW)), len(hourly(raw, NOW)))

    def test_insufficient_and_no_supply(self):
        self.assertEqual(analyze(item(), history()[-4:], fee_config())['status'], 'insufficient')
        self.assertEqual(analyze(item(None), [], CONFIG)['status'], 'unavailable')
        self.assertNotEqual(analyze({**item(), 'listed':0}, history(), fee_config())['status'], 'opportunity')

    def test_week_history_required(self):
        self.assertNotEqual(analyze(item(), history()[-25:], fee_config())['status'], 'opportunity')

    def test_fees_reject_invalid(self):
        for value in [-.1, 1, float('nan')]:
            cfg = fee_config(); cfg['fee']['sale_rate'] = value
            with self.assertRaises(ValueError): validate_config(cfg)

    def test_backtest_future_used_for_outcome_only(self):
        points = history() + [{**item(1000), 'at':iso(NOW + timedelta(hours=1))}]
        result = evaluate({'123':points}, fee_config())
        self.assertTrue(result['trades'])
        self.assertEqual(result['trades'][0]['outcome'], 'target_observed')
        self.assertEqual(result['trades'][0]['target'], 1000)
        self.assertFalse(evaluate({'123':points}, CONFIG)['enabled'])


class PipelineTests(unittest.TestCase):
    def test_failure_preserves_report_and_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'site/data/report.json'
            write_json(path, {'generated_at': AT, 'items': []})
            before = path.read_bytes()
            collector = Collector(CONFIG['collection'])
            with patch.object(collector, 'collect', side_effect=SourceError('changed HTML')):
                self.assertFalse(run(root, CONFIG, collector, NOW))
            self.assertEqual(before, path.read_bytes())
            self.assertFalse(read_json(root / 'site/data/status.json')['ok'])

    def test_stale_data_rejected(self):
        collector = Collector(CONFIG['collection'])
        with tempfile.TemporaryDirectory() as temp, patch.object(collector, 'collect', return_value=([item()], iso(NOW - timedelta(hours=4)))):
            self.assertFalse(run(Path(temp), CONFIG, collector, NOW))
            self.assertFalse((Path(temp) / 'site/data/report.json').exists())

    def test_dedup_retention(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            points = history() + history() + [{'id':'123','at':iso(NOW-timedelta(days=31)),'price':1,'listed':2}]
            save_history(root, {'123':points}, NOW, 30)
            self.assertEqual(len(load_history(root)['123']),len(history()))

    def test_repeat_source_avoids_detail_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_json(root / 'site/data/report.json', {'generated_at':AT,'items':[item()]})
            save_history(root, {'123':history()}, NOW, 30)
            collector = Collector(CONFIG['collection'])
            with patch.object(collector,'collect',return_value=([item()],AT)), patch.object(collector,'get') as get:
                self.assertTrue(run(root, CONFIG, collector, NOW))
                get.assert_not_called()


class EmailTests(unittest.TestCase):
    def report(self):
        from dftrader.analysis import make_report
        return make_report([item()], {'123':history()}, fee_config(), NOW)

    def test_new_changed_and_duplicate(self):
        report = self.report()
        self.assertEqual(len(select_alerts(report, {'ok':True}, {}, NOW)),1)
        state = {'123':{'at':AT,'price':800,'margin':15.88}}
        self.assertEqual(select_alerts(report, {'ok':True}, state, NOW),[])
        later = copy.deepcopy(report); later['items'][0]['at'] = iso(NOW)
        self.assertEqual(select_alerts(later, {'ok':True}, state, NOW),[])
        later['items'][0]['price'] = 700
        self.assertEqual(len(select_alerts(later, {'ok':True}, state, NOW)),1)

    def test_failed_stale_unknown_fee_no_alerts(self):
        report = self.report()
        self.assertEqual(select_alerts(report, {'ok':False}, {}, NOW),[])
        self.assertEqual(select_alerts(report, {'ok':True}, {}, NOW + timedelta(hours=4)),[])
        report['fee_confirmed'] = False
        self.assertEqual(select_alerts(report, {'ok':True}, {}, NOW),[])

    def test_smtp_failure_preserves_report_no_secret_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); report = self.report()
            write_json(root / 'site/data/report.json', report)
            write_json(root / 'site/data/status.json', {'ok':True})
            env = {'SMTP_USER':'sender@example.test','SMTP_APP_PASSWORD':'PRIVATE_PASSWORD','ALERT_EMAIL':'recipient@example.test'}
            def fail(*args, **kwargs): raise OSError('PRIVATE_PASSWORD')
            with patch('builtins.print') as output:
                self.assertFalse(notify(root, env, fail, NOW))
            self.assertNotIn('PRIVATE_PASSWORD',str(output.call_args_list))
            self.assertEqual(read_json(root / 'site/data/report.json'), report)
            self.assertFalse((root/'state/alerts.json').exists())

    def test_success_sends_only_owner_and_persists_public_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_json(root / 'site/data/report.json', self.report())
            write_json(root / 'site/data/status.json', {'ok':True})
            env = {'SMTP_USER':'sender@example.test','SMTP_APP_PASSWORD':'PRIVATE_PASSWORD','ALERT_EMAIL':'owner@example.test'}
            from unittest.mock import MagicMock
            smtp = MagicMock()
            smtp.__enter__.return_value = smtp
            with patch('builtins.print'):
                self.assertTrue(notify(root, env, lambda *a, **k:smtp, NOW))
            self.assertEqual(smtp.send_message.call_args.kwargs['to_addrs'], ['owner@example.test'])
            text = (root / 'state/alerts.json').read_text()
            self.assertNotIn('example.test', text)
            self.assertNotIn('PRIVATE_PASSWORD', text)
            self.assertEqual(select_alerts(self.report(), {'ok':True}, json.loads(text), NOW), [])


if __name__ == '__main__':
    unittest.main()
