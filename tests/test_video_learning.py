import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tools import video_learning


class VideoLearningTests(unittest.TestCase):
    def test_normalizes_douyin_and_xhs_records(self):
        douyin = {
            "aweme_id": "a1",
            "title": "#赚钱 普通人做自媒体",
            "desc": "每天写作和拍短视频",
            "nickname": "作者A",
            "liked_count": "100",
            "collected_count": "80",
            "comment_count": "20",
            "share_count": "40",
            "aweme_url": "https://example.com/a1",
            "video_download_url": "https://example.com/a1.mp4",
        }
        xhs = {
            "note_id": "n1",
            "title": "一人食备餐指南",
            "desc": "一周减脂餐",
            "nickname": "作者B",
            "liked_count": "10",
            "collected_count": "90",
            "comment_count": "5",
            "share_count": "7",
            "tag_list": "一人食,减脂餐,备餐",
            "note_url": "https://example.com/n1",
            "image_list": "https://sns-webpic-qc.xhscdn.com/a.webp, https://sns-webpic-qc.xhscdn.com/b.webp",
        }

        d = video_learning.normalize_record("douyin", douyin, Path("数据/douyin/json/作者A/douyin.json"))
        x = video_learning.normalize_record("xhs", xhs, Path("数据/xhs/json/作者B/xhs.json"))

        self.assertEqual(d.platform, "douyin")
        self.assertEqual(d.source_id, "a1")
        self.assertEqual(d.metrics["shares"], 40)
        self.assertEqual(d.url, "https://example.com/a1")
        self.assertEqual(d.video_download_url, "https://example.com/a1.mp4")
        self.assertEqual(d.account_name, "作者A")
        self.assertEqual(x.platform, "xhs")
        self.assertEqual(x.source_id, "n1")
        self.assertEqual(x.tags, ["一人食", "减脂餐", "备餐"])
        self.assertEqual(x.metrics["collects"], 90)
        self.assertEqual(x.account_name, "作者B")
        self.assertEqual(
            x.image_urls,
            ["https://sns-webpic-qc.xhscdn.com/a.webp", "https://sns-webpic-qc.xhscdn.com/b.webp"],
        )

    def test_load_records_detects_account_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jiang = root / "数据" / "douyin" / "json" / "姜胡说"
            li = root / "数据" / "douyin" / "json" / "李宗恒"
            xhs = root / "数据" / "xhs" / "json" / "省钱也要喂饱自己（沪漂版）"
            jiang.mkdir(parents=True)
            li.mkdir(parents=True)
            xhs.mkdir(parents=True)
            (jiang / "creator_contents.json").write_text(json.dumps([{"aweme_id": "a1", "title": "赚钱", "desc": "方法"}], ensure_ascii=False), encoding="utf-8")
            (li / "creator_contents.json").write_text(json.dumps([{"aweme_id": "a2", "title": "职场", "desc": "沟通"}], ensure_ascii=False), encoding="utf-8")
            (xhs / "creator_contents.json").write_text(json.dumps([{"note_id": "n1", "title": "一人食", "desc": "减脂餐"}], ensure_ascii=False), encoding="utf-8")

            records, raw_counts = video_learning.load_records(root)

            self.assertEqual(raw_counts["douyin_contents"], 2)
            self.assertEqual(raw_counts["xhs_contents"], 1)
            self.assertEqual({record.account_name for record in records}, {"姜胡说", "李宗恒", "省钱也要喂饱自己（沪漂版）"})

    def test_load_records_detailed_continues_after_broken_json_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json" / "姜胡说"
            data_dir.mkdir(parents=True)
            (data_dir / "broken.json").write_text('{"broken": ', encoding="utf-8")
            (data_dir / "valid.json").write_text(
                json.dumps([{"aweme_id": "a1", "title": "赚钱", "desc": "方法"}], ensure_ascii=False),
                encoding="utf-8",
            )

            records, raw_counts, failed_files = video_learning.load_records_detailed(root)

            self.assertEqual([record.source_id for record in records], ["a1"])
            self.assertEqual(raw_counts["douyin_contents"], 1)
            self.assertEqual(len(failed_files), 1)
            self.assertEqual(failed_files[0]["path"], "数据/douyin/json/姜胡说/broken.json")
            self.assertEqual(failed_files[0]["stage"], "json_decode")
            self.assertEqual(failed_files[0]["error_type"], "JSONDecodeError")

    def test_load_records_detailed_isolates_valid_json_with_invalid_record_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json" / "姜胡说"
            data_dir.mkdir(parents=True)
            (data_dir / "invalid_rows.json").write_text(
                json.dumps(["not-an-object"], ensure_ascii=False),
                encoding="utf-8",
            )
            (data_dir / "valid.json").write_text(
                json.dumps([{"aweme_id": "a1", "title": "赚钱", "desc": "方法"}], ensure_ascii=False),
                encoding="utf-8",
            )

            records, raw_counts, failed_files = video_learning.load_records_detailed(root)

            self.assertEqual([record.source_id for record in records], ["a1"])
            self.assertEqual(raw_counts["douyin_contents"], 1)
            self.assertEqual(len(failed_files), 1)
            self.assertEqual(failed_files[0]["path"], "数据/douyin/json/姜胡说/invalid_rows.json")
            self.assertEqual(failed_files[0]["stage"], "record_validation")

    def test_select_deep_learning_reports_source_file_failures_without_stopping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json" / "姜胡说"
            data_dir.mkdir(parents=True)
            (data_dir / "broken.json").write_text('{"broken": ', encoding="utf-8")
            (data_dir / "valid.json").write_text(
                json.dumps([{"aweme_id": "a1", "title": "赚钱", "desc": "方法"}], ensure_ascii=False),
                encoding="utf-8",
            )

            result = video_learning.select_deep_learning(root, source_ids={"a1"})

            self.assertEqual(result["selected"], 1)
            self.assertTrue(result["partial_success"])
            self.assertEqual(result["failed_files"][0]["path"], "数据/douyin/json/姜胡说/broken.json")

    def test_direction_detection_and_platform_heat_scores(self):
        douyin_record = video_learning.NormalizedRecord(
            platform="douyin",
            source_id="a1",
            source_file="douyin.json",
            title="#赚钱 普通人做自媒体",
            body="创业 方法 短视频",
            author_name="作者A",
            published_at="",
            metrics={"likes": 100, "collects": 80, "comments": 20, "shares": 40},
            tags=["赚钱", "自媒体"],
            url="",
            video_download_url="",
            text_fingerprint="fp1",
        )
        xhs_record = video_learning.NormalizedRecord(
            platform="xhs",
            source_id="n1",
            source_file="xhs.json",
            title="一人食备餐指南",
            body="一周减脂餐",
            author_name="作者B",
            published_at="",
            metrics={"likes": 10, "collects": 90, "comments": 5, "shares": 7},
            tags=["一人食", "减脂餐", "备餐"],
            url="",
            video_download_url="",
            text_fingerprint="fp2",
        )

        self.assertIn("赚钱", video_learning.detect_directions(douyin_record))
        self.assertIn("自媒体", video_learning.detect_directions(douyin_record))
        self.assertIn("减脂餐", video_learning.detect_directions(xhs_record))
        self.assertAlmostEqual(video_learning.heat_score(douyin_record), 60.0)
        self.assertAlmostEqual(video_learning.heat_score(xhs_record), 45.05)

    def test_lizongheng_content_gets_account_specific_directions(self):
        record = video_learning.NormalizedRecord(
            platform="douyin",
            source_id="l1",
            source_file="数据/douyin/json/李宗恒/creator_contents.json",
            title="《去同学家做客的社死时刻》 #李宗恒 #大学生 #内容过于真实",
            body="校园宿舍社死反转剧情",
            author_name="李宗恒",
            published_at="",
            metrics={"likes": 100, "collects": 10, "comments": 5, "shares": 20},
            tags=["李宗恒", "大学生", "内容过于真实"],
            url="",
            video_download_url="",
            text_fingerprint="fp",
            account_name="李宗恒",
        )

        directions = video_learning.detect_directions(record)

        self.assertIn("剧情短剧", directions)
        self.assertIn("校园大学生", directions)
        self.assertIn("喜剧反转", directions)

    def test_lizongheng_uncategorized_patterns_get_specific_directions(self):
        cases = [
            ("一个扶梯 两种爱情", ["爱情关系喜剧", "生活荒诞反转"]),
            ("《00后销售》 #李宗恒", ["代际观察", "身份错位短剧"]),
            ("社恐版？？？#李宗恒", ["性格标签喜剧", "人际社交观察"]),
            ("《前任驾校？》#李宗恒", ["爱情关系喜剧", "身份错位短剧"]),
            ("《当生日许愿遇上了编剧》 #李宗恒 #生日", ["生活荒诞反转", "剧情短剧"]),
            ("《中文十级教学》 #李宗恒", ["语言表达喜剧"]),
            ("《举手的心理战》 #李宗恒", ["心理博弈"]),
            ("哄好自己！ #李宗恒", ["情绪自洽"]),
            ("《准时下班！》 #李宗恒", ["职场关系"]),
            ("如果这样上课，大家能认真听吧！", ["校园大学生", "身份错位短剧"]),
            ("你可能不认识我，但这些都没看过嘛？ #李宗恒", ["作品代表作索引"]),
            ("《这怎么还不帮我了呢？》#李宗恒", ["求助边界拉扯"]),
            ("《不忘初心 砥砺前行》#李宗恒", ["口号仪式反讽"]),
            ("失眠部门…#李宗恒", ["部门组织拟人"]),
            ("《当你过年强的可怕！》 #李宗恒", ["节日家庭场景"]),
            ("我暗示的还不够明显吗？ #李宗恒", ["暗示沟通"]),
            ("最有礼貌！ @大伟老三 #李宗恒", ["礼貌社交规则"]),
            ("《家庭业务中心》 #李宗恒", ["部门组织拟人", "节日家庭场景"]),
            ("当霸总暑假去学车？？？ #李宗恒", ["身份错位短剧"]),
            ("《以前有钢铁直男，现在有拿铁直男》#李宗恒", ["性格标签喜剧"]),
            ("当我第一次坐商务座 #李宗恒", ["消费体验反差"]),
            ("你们下次就这么和对象吵架～ #李宗恒", ["爱情关系喜剧", "冲突吵架技巧"]),
            ("《如此AA》 #李宗恒", ["金钱边界喜剧"]),
            ("《如此“叛逆”》#李宗恒", ["叛逆反差"]),
            ("《我要睡觉！》#李宗恒", ["身体状态喜剧"]),
            ("被迫饿了…#李宗恒", ["身体状态喜剧"]),
            ("《男女之间真的有纯友谊吗？》#李宗恒", ["爱情关系喜剧", "朋友熟人关系"]),
            ("每天绞尽脑汁，只为了朋友那一句：你有病啊！ #李宗恒", ["朋友熟人关系"]),
            ("《增强自信》 @钟婷xo #李宗恒", ["自信夸奖喜剧"]),
            ("《如此心眼子》#李宗恒", ["心眼疑心拟人"]),
            ("《好像哪里不对呢…》#李宗恒", ["沟通误解喜剧"]),
            ("这啥理由啊？？？#李宗恒", ["沟通误解喜剧"]),
            ("这是啥打招呼方式？ #李宗恒", ["沟通误解喜剧"]),
            ("《太难了！》#李宗恒", ["压力崩溃喜剧"]),
            ("《如此点菜》 @大伟老三 #李宗恒", ["吃饭点菜场景"]),
            ("关于商战的那点事儿#李宗恒", ["商战利益博弈"]),
            ("第一次见家长，竟然…#李宗恒", ["家庭身份关系"]),
        ]
        for title, expected in cases:
            record = video_learning.NormalizedRecord(
                platform="douyin",
                source_id=title,
                source_file="数据/douyin/json/李宗恒/creator_contents.json",
                title=title,
                body="",
                author_name="李宗恒",
                published_at="",
                metrics={"likes": 1, "collects": 1, "comments": 1, "shares": 1},
                tags=[],
                url="",
                video_download_url="",
                text_fingerprint=title,
                account_name="李宗恒",
            )
            directions = video_learning.detect_directions(record)
            for direction in expected:
                self.assertIn(direction, directions, title)

    def test_jianghushuo_uncategorized_patterns_get_specific_directions(self):
        cases = [
            ("作弊 这个世界是可以作弊的", ["人生策略"]),
            ("跟对大哥 借大哥的视野看世界 学会用梯子", ["借势杠杆", "人生策略"]),
            ("聚宝盆 生意场上无论信息大小，出卖的都是智慧", ["商业机会"]),
            ("脱离了生活的 #文案 ，是没有灵魂的", ["表达文案"]),
            ("基础技能 学会销售，学会构建", ["技能资产"]),
            ("就3句话：知道有念，知道无念，知道就行。", ["心智修炼"]),
            ("我不带大家炒G，不推荐个G。请大家一定要小心。", ["风险避坑"]),
            ("推荐几本书 #姜胡说", ["阅读输入"]),
            ("当上帝来敲门的时候，你应该在家。", ["机会准备"]),
            ("像我这样的人，不应该成为你知识的主要来源。", ["信息源判断"]),
            ("让我们像高手一样思考", ["高手思考模型"]),
            ("我每一天都在进化。脸这个东西，越无能的人看的越重。", ["自我进化"]),
            ("真正理解了那些最关键的知识，人生就改变了。", ["关键知识"]),
            ("第一性原理，目的是什么？穷举一切手段；剃刀法则，保持足够简单。", ["高手思考模型"]),
            ("城镇化、工业化；服务、消费+互联网；新能源车、碳中和、高精尖", ["宏观趋势"]),
            ("知道自己不厉害，这很重要。", ["自知谦逊"]),
            ("做小事 平淡的事 做好 做完整 保持专注 全情投入", ["做事框架"]),
            ("思考“思考的过程”", ["高手思考模型"]),
            ("人生算法", ["人生策略", "高手思考模型"]),
            ("知识、结构、函数调用 #姜胡说", ["结构化理解"]),
            ("给你的人生编程", ["结构化理解"]),
            ("对抗熵增", ["做事框架"]),
            ("希望你能更早的理解到这句话的意思。 #芬钛计划 #牛市来了吗", ["市场周期理解"]),
            ("如果完成一件看似不可能的事", ["做事框架"]),
            ("深度思考", ["高手思考模型"]),
            ("我的转型之路", ["自我进化"]),
            ("重新梳理对这个世界的理解", ["结构化理解"]),
            ("我对当下市场的理解&会议解读框架", ["市场周期理解", "做事框架"]),
            ("普通人应该掌握的几个原理、法则", ["高手思考模型"]),
            ("重新理解计划", ["做事框架"]),
            ("重新思考", ["高手思考模型"]),
            ("重新理解", ["结构化理解"]),
        ]
        for title, expected in cases:
            record = video_learning.NormalizedRecord(
                platform="douyin",
                source_id=title,
                source_file="数据/douyin/json/姜胡说/creator_contents.json",
                title=title,
                body="",
                author_name="姜胡说",
                published_at="",
                metrics={"likes": 1, "collects": 1, "comments": 1, "shares": 1},
                tags=[],
                url="",
                video_download_url="",
                text_fingerprint=title,
                account_name="姜胡说",
            )
            directions = video_learning.detect_directions(record)
            for direction in expected:
                self.assertIn(direction, directions, title)

    def test_account_specific_directions_do_not_cross_accounts(self):
        jiang_record = video_learning.NormalizedRecord(
            platform="douyin",
            source_id="j-cross",
            source_file="数据/douyin/json/姜胡说/creator_contents.json",
            title="朋友之间也可以讨论商战和博弈，关键是做好自己的事",
            body="",
            author_name="姜胡说",
            published_at="",
            metrics={"likes": 1, "collects": 1, "comments": 1, "shares": 1},
            tags=[],
            url="",
            video_download_url="",
            text_fingerprint="j-cross",
            account_name="姜胡说",
        )
        li_record = video_learning.NormalizedRecord(
            platform="douyin",
            source_id="l-cross",
            source_file="数据/douyin/json/李宗恒/creator_contents.json",
            title="人生算法和第一性原理",
            body="",
            author_name="李宗恒",
            published_at="",
            metrics={"likes": 1, "collects": 1, "comments": 1, "shares": 1},
            tags=[],
            url="",
            video_download_url="",
            text_fingerprint="l-cross",
            account_name="李宗恒",
        )

        self.assertNotIn("朋友熟人关系", video_learning.detect_directions(jiang_record))
        self.assertNotIn("商战利益博弈", video_learning.detect_directions(jiang_record))
        self.assertNotIn("人生策略", video_learning.detect_directions(li_record))
        self.assertNotIn("高手思考模型", video_learning.detect_directions(li_record))

    def test_splits_and_validates_xhs_image_urls(self):
        urls = video_learning.split_image_urls(" https://sns-webpic-qc.xhscdn.com/a.webp,https://sns-img-qc.xhscdn.com/b.webp,, ")

        self.assertEqual(urls, ["https://sns-webpic-qc.xhscdn.com/a.webp", "https://sns-img-qc.xhscdn.com/b.webp"])
        self.assertTrue(video_learning.is_allowed_image_url("https://sns-webpic-qc.xhscdn.com/a.webp"))
        self.assertTrue(video_learning.is_allowed_image_url("http://sns-img-qc.xhscdn.com/b.webp"))
        self.assertFalse(video_learning.is_allowed_image_url("ftp://sns-webpic-qc.xhscdn.com/a.webp"))
        self.assertFalse(video_learning.is_allowed_image_url("https://example.com/a.webp"))

    def test_image_status_is_metadata_only_without_analyze_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = video_learning.NormalizedRecord(
                platform="xhs",
                source_id="n1",
                source_file="xhs.json",
                title="一人食",
                body="减脂餐",
                author_name="作者",
                published_at="",
                metrics={"likes": 1, "collects": 1, "comments": 1, "shares": 1},
                tags=[],
                url="",
                video_download_url="",
                text_fingerprint="fp",
                image_urls=["https://sns-webpic-qc.xhscdn.com/a.webp"],
            )

            status = video_learning.image_status(root, record, analyze_images=False)

            self.assertEqual(status["status"], "metadata_only")
            self.assertFalse((root / "00_System" / "runtime" / "cache" / "video_learning" / "image_artifacts").exists())

    def test_image_status_downloads_indexes_and_ocr_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_image = root / "source.png"
            Image.new("RGB", (120, 80), "white").save(source_image)
            record = video_learning.NormalizedRecord(
                platform="xhs",
                source_id="n1",
                source_file="xhs.json",
                title="一人食",
                body="减脂餐",
                author_name="作者",
                published_at="",
                metrics={"likes": 1, "collects": 1, "comments": 1, "shares": 1},
                tags=[],
                url="",
                video_download_url="",
                text_fingerprint="fp",
                image_urls=[
                    "https://sns-webpic-qc.xhscdn.com/a.webp",
                    "https://example.com/blocked.webp",
                    "https://sns-webpic-qc.xhscdn.com/b.webp",
                ],
            )

            def fake_urlretrieve(url, filename):
                shutil.copyfile(source_image, filename)
                return filename, {}

            with patch("tools.video_learning.download_image_url", side_effect=lambda url, filename: fake_urlretrieve(url, filename)), patch(
                "tools.video_learning.ocr_image", return_value="一周不重样减脂餐"
            ):
                status = video_learning.image_status(root, record, analyze_images=True, max_images_per_note=1)

            index_path = root / "00_System" / "runtime" / "cache" / "video_learning" / "image_artifacts" / "xhs_n1" / "image_index.json"
            self.assertEqual(status["status"], "images_downloaded_ocr_completed")
            self.assertTrue(status["truncated"])
            self.assertEqual(status["downloaded_count"], 1)
            self.assertEqual(status["ocr_success_count"], 1)
            self.assertTrue(index_path.exists())
            index = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(index["images"][0]["ocr_text"], "一周不重样减脂餐")
            self.assertEqual(index["images"][0]["width"], 120)
            self.assertEqual(index["images"][0]["height"], 80)

    def test_download_image_url_sends_browser_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "image.webp"
            captured = {}

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return b"image-bytes"

            def fake_urlopen(request, timeout):
                captured["request"] = request
                captured["timeout"] = timeout
                return FakeResponse()

            with patch("tools.video_learning.urllib.request.urlopen", side_effect=fake_urlopen):
                video_learning.download_image_url("https://sns-webpic-qc.xhscdn.com/a.webp", target)

            self.assertEqual(target.read_bytes(), b"image-bytes")
            self.assertIn("Mozilla", captured["request"].headers["User-agent"])
            self.assertIn("xiaohongshu.com", captured["request"].headers["Referer"])
            self.assertEqual(captured["timeout"], 30)

    def test_download_image_url_retries_https_for_http_403(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "image.webp"
            requested_urls = []

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return b"image-bytes"

            def fake_urlopen(request, timeout):
                requested_urls.append(request.full_url)
                if request.full_url.startswith("http://"):
                    raise video_learning.urllib.error.HTTPError(request.full_url, 403, "Forbidden", None, None)
                return FakeResponse()

            with patch("tools.video_learning.urllib.request.urlopen", side_effect=fake_urlopen):
                video_learning.download_image_url("http://sns-webpic-qc.xhscdn.com/a.webp", target)

            self.assertEqual(
                requested_urls,
                ["http://sns-webpic-qc.xhscdn.com/a.webp", "https://sns-webpic-qc.xhscdn.com/a.webp"],
            )
            self.assertEqual(target.read_bytes(), b"image-bytes")

    def test_download_binary_url_uses_timeout_and_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "source.mp4"
            captured = {}

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return b"video-bytes"

            def fake_urlopen(request, timeout):
                captured["request"] = request
                captured["timeout"] = timeout
                return FakeResponse()

            with patch("tools.video_learning.find_executable", return_value=""), patch(
                "tools.video_learning.urllib.request.urlopen", side_effect=fake_urlopen
            ):
                video_learning.download_binary_url("https://example.com/video.mp4", target)

            self.assertEqual(target.read_bytes(), b"video-bytes")
            self.assertIn("Mozilla", captured["request"].headers["User-agent"])
            self.assertEqual(captured["timeout"], 300)

    def test_download_binary_url_prefers_curl_with_total_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "source.mp4"
            captured = {}

            def fake_run(cmd, check, capture_output, text, timeout):
                captured["cmd"] = cmd
                captured["timeout"] = timeout
                target.write_bytes(b"video-bytes")

            with patch("tools.video_learning.find_executable", return_value="/usr/bin/curl"), patch(
                "tools.video_learning.subprocess.run", side_effect=fake_run
            ):
                video_learning.download_binary_url("https://example.com/video.mp4", target)

            self.assertEqual(target.read_bytes(), b"video-bytes")
            self.assertIn("--max-time", captured["cmd"])
            self.assertIn("300", captured["cmd"])
            self.assertIn("--connect-timeout", captured["cmd"])
            self.assertIn("--retry", captured["cmd"])
            self.assertIn("--retry-all-errors", captured["cmd"])
            self.assertIn("--speed-time", captured["cmd"])
            self.assertIn("Referer: https://www.douyin.com/", captured["cmd"])
            self.assertEqual(captured["timeout"], 330)

    def test_ensure_video_file_continues_when_download_reports_error_but_file_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "source.mp4"

            def fake_download(url, path):
                path.write_bytes(b"valid-video-bytes")
                raise RuntimeError("curl timed out")

            with patch("tools.video_learning.download_binary_url", side_effect=fake_download), patch(
                "tools.video_learning.media_file_is_readable", side_effect=[False, True]
            ), patch(
                "tools.video_learning.media_file_decodes", return_value=True
            ):
                warnings = video_learning.ensure_video_file("https://example.com/video.mp4", target)

            self.assertEqual(target.read_bytes(), b"valid-video-bytes")
            self.assertEqual(len(warnings), 1)
            self.assertIn("download_reported_error_but_file_is_usable", warnings[0])

    def test_ensure_video_file_reuses_existing_valid_source_without_redownload(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "source.mp4"
            target.write_bytes(b"existing-video")

            with patch("tools.video_learning.download_binary_url") as download, patch(
                "tools.video_learning.media_file_is_readable", return_value=True
            ), patch(
                "tools.video_learning.media_file_decodes", return_value=True
            ):
                warnings = video_learning.ensure_video_file("https://example.com/video.mp4", target)

            download.assert_not_called()
            self.assertEqual(warnings, ["using_existing_video_file"])

    def test_ensure_video_file_redownloads_existing_readable_but_corrupt_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "source.mp4"
            target.write_bytes(b"corrupt-video")

            def fake_download(url, path):
                path.write_bytes(b"fixed-video")

            with patch("tools.video_learning.download_binary_url", side_effect=fake_download) as download, patch(
                "tools.video_learning.media_file_is_readable", return_value=True
            ), patch(
                "tools.video_learning.media_file_decodes", side_effect=[False, True]
            ):
                warnings = video_learning.ensure_video_file("https://example.com/video.mp4", target)

            download.assert_called_once()
            self.assertEqual(target.read_bytes(), b"fixed-video")
            self.assertEqual(warnings, [])

    def test_ensure_video_file_preserves_existing_source_and_partial_replacement_when_download_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "source.mp4"
            target.write_bytes(b"existing-corrupt-video")

            def fake_download(url, path):
                path.write_bytes(b"partial-replacement")
                raise RuntimeError("curl timed out")

            with patch("tools.video_learning.download_binary_url", side_effect=fake_download), patch(
                "tools.video_learning.media_file_is_readable", return_value=True
            ), patch(
                "tools.video_learning.media_file_decodes", return_value=False
            ):
                with self.assertRaisesRegex(RuntimeError, "curl timed out"):
                    video_learning.ensure_video_file("https://example.com/video.mp4", target)

            self.assertEqual(target.read_bytes(), b"existing-corrupt-video")
            self.assertEqual((target.parent / "source.mp4.download").read_bytes(), b"partial-replacement")

    def test_download_binary_url_resumes_existing_partial_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "source.mp4.download"
            target.write_bytes(b"partial")
            captured = {}

            def fake_run(cmd, check, capture_output, text, timeout):
                captured["cmd"] = cmd

            with patch("tools.video_learning.find_executable", return_value="/usr/bin/curl"), patch(
                "tools.video_learning.subprocess.run", side_effect=fake_run
            ):
                video_learning.download_binary_url("https://example.com/video.mp4", target)

            self.assertIn("--continue-at", captured["cmd"])
            self.assertIn("-", captured["cmd"])
            retry_index = captured["cmd"].index("--retry")
            self.assertEqual(captured["cmd"][retry_index + 1], "0")
            max_time_index = captured["cmd"].index("--max-time")
            self.assertEqual(captured["cmd"][max_time_index + 1], "1800")

    def test_existing_video_bundle_rejects_transcript_that_does_not_cover_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            video_path = artifact_dir / "source.mp4"
            audio_path = artifact_dir / "audio.wav"
            metadata_path = artifact_dir / "ffprobe.json"
            transcript_json_path = artifact_dir / "transcript.json"
            transcript_srt_path = artifact_dir / "transcript.srt"
            scene_path = artifact_dir / "source-Scenes.csv"
            for path in (video_path, audio_path, metadata_path, transcript_srt_path, scene_path):
                path.write_text("present", encoding="utf-8")
            transcript_json_path.write_text(
                json.dumps({"segments": [{"start": 60.0, "end": 68.0, "text": "partial"}]}),
                encoding="utf-8",
            )

            bundle_check = getattr(video_learning, "existing_video_bundle_is_complete", lambda *args: True)
            with patch("tools.video_learning.media_file_is_usable", return_value=True), patch(
                "tools.video_learning.media_duration_seconds", return_value=100.0, create=True
            ):
                complete = bundle_check(
                    video_path,
                    audio_path,
                    metadata_path,
                    transcript_json_path,
                    transcript_srt_path,
                    [scene_path],
                )

            self.assertFalse(complete)

    def test_image_analysis_respects_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "xhs" / "json" / "作者"
            data_dir.mkdir(parents=True)
            rows = [
                {
                    "note_id": f"n{index}",
                    "title": "一人食备餐指南",
                    "desc": "一周减脂餐",
                    "nickname": "作者",
                    "liked_count": str(100 + index),
                    "collected_count": str(100 + index),
                    "comment_count": str(30 + index),
                    "share_count": str(40 + index),
                    "note_url": f"https://example.com/{index}",
                    "image_list": f"https://sns-webpic-qc.xhscdn.com/{index}.webp",
                }
                for index in range(3)
            ]
            (data_dir / "creator_contents_test.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            calls = []
            original = video_learning.image_status

            def fake_image_status(root_path, record, analyze_images, max_images_per_note=18):
                calls.append(analyze_images)
                return {
                    "requested": analyze_images,
                    "has_image_urls": bool(record.image_urls),
                    "status": "fake",
                    "downloaded_count": 0,
                    "ocr_success_count": 0,
                    "images": [],
                    "errors": [],
                    "truncated": False,
                }

            try:
                video_learning.image_status = fake_image_status
                video_learning.run_pipeline(root, analyze_images=True, image_limit=1)
            finally:
                video_learning.image_status = original

            self.assertEqual(calls.count(True), 1)
            self.assertGreaterEqual(calls.count(False), 1)

    def test_deduplicates_by_source_id_and_text_fingerprint(self):
        first = video_learning.NormalizedRecord(
            platform="douyin",
            source_id="a1",
            source_file="old.json",
            title="标题",
            body="内容",
            author_name="作者",
            published_at="",
            metrics={"likes": 10, "collects": 10, "comments": 1, "shares": 1},
            tags=[],
            url="",
            video_download_url="",
            text_fingerprint="same",
        )
        newer = video_learning.NormalizedRecord(
            platform="douyin",
            source_id="a1",
            source_file="new.json",
            title="标题",
            body="内容",
            author_name="作者",
            published_at="",
            metrics={"likes": 20, "collects": 20, "comments": 2, "shares": 2},
            tags=[],
            url="",
            video_download_url="",
            text_fingerprint="same",
        )

        records, stats = video_learning.deduplicate_records([first, newer])

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source_file, "new.json")
        self.assertEqual(stats["duplicate_source_id"], 1)

    def test_builds_direction_rankings_with_top10_limit(self):
        records = []
        for index in range(12):
            records.append(
                video_learning.NormalizedRecord(
                    platform="douyin",
                    source_id=f"a{index}",
                    source_file="douyin.json",
                    title="#赚钱",
                    body="创业 自媒体",
                    author_name="作者",
                    published_at="",
                    metrics={
                        "likes": index,
                        "collects": index,
                        "comments": index,
                        "shares": index,
                    },
                    tags=["赚钱"],
                    url=f"https://example.com/{index}",
                    video_download_url="",
                    text_fingerprint=f"fp{index}",
                )
            )

        rankings = video_learning.build_direction_rankings(records)

        self.assertEqual(len(rankings["赚钱"]), 10)
        self.assertEqual(rankings["赚钱"][0].record.source_id, "a11")
        self.assertEqual(rankings["赚钱"][-1].record.source_id, "a2")

    def test_writes_report_cards_and_formal_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json"
            data_dir.mkdir(parents=True)
            (root / "00_System" / "runtime" / "reports" / "video_learning").mkdir(parents=True)
            (root / "10_Knowledge" / "formal" / "methods").mkdir(parents=True)
            (root / "10_Knowledge" / "formal" / "topics").mkdir(parents=True)
            (root / "10_Knowledge" / "formal" / "content_factory").mkdir(parents=True)
            (root / "10_Knowledge" / "formal" / "methods" / "抖音爆款方法论_v1.md").write_text("# 抖音\n", encoding="utf-8")
            (root / "10_Knowledge" / "formal" / "topics" / "选题灵感库_v1.md").write_text("# 选题\n", encoding="utf-8")
            (root / "10_Knowledge" / "formal" / "content_factory" / "内容生产模板_v1.md").write_text("# 模板\n", encoding="utf-8")
            stale_dir = root / "10_Knowledge" / "candidates" / "learning_cards" / "deep_cards"
            stale_dir.mkdir(parents=True)
            (stale_dir / "douyin_a9.md").write_text("stale", encoding="utf-8")

            rows = [
                {
                    "aweme_id": f"a{index}",
                    "title": "#赚钱 普通人做自媒体",
                    "desc": "创业 方法 短视频，每天写作和拍视频",
                    "nickname": "作者",
                    "liked_count": str(100 + index),
                    "collected_count": str(100 + index),
                    "comment_count": str(30 + index),
                    "share_count": str(40 + index),
                    "aweme_url": f"https://example.com/{index}",
                    "video_download_url": "",
                }
                for index in range(10)
            ]
            (data_dir / "creator_contents_test.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

            result = video_learning.run_pipeline(root, apply=True, analyze_video=False)

            report = root / "00_System" / "runtime" / "reports" / "video_learning" / "latest_scan_report.md"
            inventory_md = root / "00_System" / "runtime" / "reports" / "video_learning" / "initial_knowledge" / "latest_content_inventory.md"
            inventory_jsonl = root / "00_System" / "runtime" / "reports" / "video_learning" / "initial_knowledge" / "latest_content_inventory.jsonl"
            topic_pool_md = root / "00_System" / "runtime" / "reports" / "video_learning" / "initial_knowledge" / "latest_topic_pool.md"
            direction_matrix_md = root / "00_System" / "runtime" / "reports" / "video_learning" / "initial_knowledge" / "latest_direction_matrix.md"
            account_card = root / "10_Knowledge" / "candidates" / "account_assets" / "account_cards" / "作者_douyin.md"
            card = root / "10_Knowledge" / "candidates" / "learning_cards" / "deep_cards" / "赚钱_douyin_a9.md"
            methods = root / "10_Knowledge" / "formal" / "methods" / "抖音爆款方法论_v1.md"
            topics = root / "10_Knowledge" / "formal" / "topics" / "选题灵感库_v1.md"

            self.assertEqual(result["raw_counts"]["douyin_contents"], 10)
            self.assertTrue(report.exists())
            self.assertTrue(inventory_md.exists())
            self.assertTrue(inventory_jsonl.exists())
            self.assertTrue(topic_pool_md.exists())
            self.assertTrue(direction_matrix_md.exists())
            self.assertTrue(account_card.exists())
            self.assertTrue(card.exists())
            self.assertIn("direction: 赚钱", card.read_text(encoding="utf-8"))
            self.assertIn("method_id: auto-douyin", methods.read_text(encoding="utf-8"))
            self.assertIn("topic_id: auto-douyin", topics.read_text(encoding="utf-8"))
            self.assertIn("账号：作者", card.read_text(encoding="utf-8"))
            self.assertIn("| 作者 | douyin | 1 |", report.read_text(encoding="utf-8"))
            self.assertIn("# 初扫知识池：内容清单", inventory_md.read_text(encoding="utf-8"))
            self.assertIn("# 初扫知识池：代选选题池", topic_pool_md.read_text(encoding="utf-8"))
            self.assertIn("# 初扫知识池：方向矩阵", direction_matrix_md.read_text(encoding="utf-8"))
            self.assertIn("\"primary_direction\": \"赚钱\"", inventory_jsonl.read_text(encoding="utf-8"))
            self.assertIn("# 账号学习卡：作者 / douyin", account_card.read_text(encoding="utf-8"))
            self.assertFalse((stale_dir / "douyin_a9.md").exists())
            self.assertGreaterEqual(len(list(stale_dir.glob("*.md"))), 5)

    def test_scan_account_filter_limits_initial_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json"
            data_dir.mkdir(parents=True)
            (root / "00_System" / "runtime" / "reports" / "video_learning").mkdir(parents=True)

            rows = [
                {
                    "aweme_id": "a1",
                    "title": "#赚钱 普通人做自媒体",
                    "desc": "创业 方法 短视频",
                    "nickname": "姜胡说",
                    "liked_count": "100",
                    "collected_count": "80",
                    "comment_count": "20",
                    "share_count": "40",
                    "aweme_url": "https://example.com/a1",
                    "video_download_url": "",
                },
                {
                    "aweme_id": "a2",
                    "title": "职场关系",
                    "desc": "沟通 反转",
                    "nickname": "李宗恒",
                    "liked_count": "10",
                    "collected_count": "5",
                    "comment_count": "2",
                    "share_count": "1",
                    "aweme_url": "https://example.com/a2",
                    "video_download_url": "",
                },
            ]
            (data_dir / "creator_contents_test.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

            result = video_learning.run_pipeline(root, apply=False, analyze_video=False, account_name="姜胡说")

            inventory_md = root / "00_System" / "runtime" / "reports" / "video_learning" / "initial_knowledge" / "latest_content_inventory.md"
            topic_pool_md = root / "00_System" / "runtime" / "reports" / "video_learning" / "initial_knowledge" / "latest_topic_pool.md"
            direction_matrix_md = root / "00_System" / "runtime" / "reports" / "video_learning" / "initial_knowledge" / "latest_direction_matrix.md"

            self.assertGreaterEqual(result["directions"], 1)
            self.assertEqual(result["account_cards"], 1)
            self.assertTrue(inventory_md.exists())
            self.assertTrue(topic_pool_md.exists())
            self.assertTrue(direction_matrix_md.exists())
            self.assertIn("账号过滤：姜胡说", inventory_md.read_text(encoding="utf-8"))
            self.assertIn("姜胡说", inventory_md.read_text(encoding="utf-8"))
            self.assertNotIn("李宗恒", inventory_md.read_text(encoding="utf-8"))
            self.assertIn("姜胡说", topic_pool_md.read_text(encoding="utf-8"))
            self.assertNotIn("李宗恒", topic_pool_md.read_text(encoding="utf-8"))
            self.assertIn("姜胡说", direction_matrix_md.read_text(encoding="utf-8"))
            self.assertNotIn("李宗恒", direction_matrix_md.read_text(encoding="utf-8"))

    def test_video_analysis_respects_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json"
            data_dir.mkdir(parents=True)
            (root / "00_System" / "runtime" / "reports" / "video_learning").mkdir(parents=True)
            rows = [
                {
                    "aweme_id": f"a{index}",
                    "title": f"#赚钱 普通人做自媒体 {index}",
                    "desc": f"创业 方法 短视频 {index}",
                    "nickname": "作者",
                    "liked_count": str(100 + index),
                    "collected_count": str(100 + index),
                    "comment_count": str(30 + index),
                    "share_count": str(40 + index),
                    "aweme_url": f"https://example.com/{index}",
                    "video_download_url": f"https://example.com/{index}.mp4",
                }
                for index in range(3)
            ]
            (data_dir / "creator_contents_test.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

            calls = []
            original = video_learning.video_status

            def fake_video_status(root_path, record, analyze_video):
                calls.append(analyze_video)
                return {
                    "requested": analyze_video,
                    "has_video_url": bool(record.video_download_url),
                    "ffmpeg": "",
                    "faster_whisper": False,
                    "scenedetect": False,
                    "status": "fake",
                    "artifacts": {},
                }

            try:
                video_learning.video_status = fake_video_status
                video_learning.run_pipeline(root, apply=False, analyze_video=True, video_limit=1)
            finally:
                video_learning.video_status = original

            self.assertEqual(calls.count(True), 1)
            self.assertGreaterEqual(calls.count(False), 1)

    def test_video_analysis_can_target_source_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json"
            data_dir.mkdir(parents=True)
            (root / "00_System" / "runtime" / "reports" / "video_learning").mkdir(parents=True)
            rows = [
                {
                    "aweme_id": f"a{index}",
                    "title": f"#赚钱 普通人做自媒体 {index}",
                    "desc": f"创业 方法 短视频 {index}",
                    "nickname": "作者",
                    "liked_count": str(100 + index),
                    "collected_count": str(100 + index),
                    "comment_count": str(30 + index),
                    "share_count": str(40 + index),
                    "aweme_url": f"https://example.com/{index}",
                    "video_download_url": f"https://example.com/{index}.mp4",
                }
                for index in range(3)
            ]
            (data_dir / "creator_contents_test.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

            analyzed = []
            original = video_learning.video_status

            def fake_video_status(root_path, record, analyze_video):
                if analyze_video:
                    analyzed.append(record.source_id)
                return {
                    "requested": analyze_video,
                    "has_video_url": bool(record.video_download_url),
                    "ffmpeg": "",
                    "faster_whisper": False,
                    "scenedetect": False,
                    "status": "fake",
                    "artifacts": {},
                }

            try:
                video_learning.video_status = fake_video_status
                video_learning.run_pipeline(root, analyze_video=True, video_limit=10, source_ids={"a1", "a2"})
            finally:
                video_learning.video_status = original

            self.assertEqual(set(analyzed), {"a1", "a2"})

    def test_video_status_is_reused_across_direction_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json"
            data_dir.mkdir(parents=True)
            (root / "00_System" / "runtime" / "reports" / "video_learning").mkdir(parents=True)
            rows = [
                {
                    "aweme_id": "a1",
                    "title": "#赚钱 普通人做自媒体",
                    "desc": "创业 方法 短视频",
                    "nickname": "作者",
                    "liked_count": "100",
                    "collected_count": "100",
                    "comment_count": "30",
                    "share_count": "40",
                    "aweme_url": "https://example.com/a1",
                    "video_download_url": "https://example.com/a1.mp4",
                }
            ]
            (data_dir / "creator_contents_test.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

            calls = []
            original = video_learning.video_status

            def fake_video_status(root_path, record, analyze_video):
                calls.append(analyze_video)
                return {
                    "requested": analyze_video,
                    "has_video_url": bool(record.video_download_url),
                    "ffmpeg": "",
                    "faster_whisper": False,
                    "scenedetect": False,
                    "status": "shared_status",
                    "artifacts": {},
                    "errors": ["same failure"],
                }

            try:
                video_learning.video_status = fake_video_status
                result = video_learning.run_pipeline(root, analyze_video=True, video_limit=1, source_ids={"a1"})
            finally:
                video_learning.video_status = original

            cards = list((root / "10_Knowledge" / "candidates" / "learning_cards" / "deep_cards").glob("*_douyin_a1.md"))
            self.assertGreaterEqual(len(cards), 2)
            self.assertEqual(calls, [True])
            for card in cards:
                self.assertIn("video_analysis_status: shared_status", card.read_text(encoding="utf-8"))
            status_path = root / "00_System" / "runtime" / "reports" / "video_learning" / "latest_video_statuses.json"
            statuses = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(statuses["douyin:a1"]["status"], "shared_status")
            self.assertEqual(result["video_analysis_requested"], 1)

    def test_select_writes_pending_deep_learning_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json" / "作者"
            data_dir.mkdir(parents=True)
            rows = [
                {
                    "aweme_id": "a1",
                    "title": "#赚钱 普通人做自媒体",
                    "desc": "创业 方法 短视频",
                    "nickname": "作者",
                    "liked_count": "100",
                    "collected_count": "100",
                    "comment_count": "30",
                    "share_count": "40",
                    "aweme_url": "https://example.com/a1",
                    "video_download_url": "https://example.com/a1.mp4",
                }
            ]
            (data_dir / "creator_contents_test.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

            result = video_learning.select_deep_learning(root, source_ids={"a1"})

            queue_path = root / "90_Temp" / "scratch" / "video_learning" / "queues" / "pending_deep_learning.json"
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
            self.assertEqual(result["queued"], 1)
            self.assertEqual(queue["items"][0]["source_id"], "a1")
            self.assertEqual(queue["items"][0]["status"], "pending")
            self.assertIn("赚钱", queue["items"][0]["directions"])

    def test_selected_learning_does_not_rewrite_scan_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json" / "作者"
            output_dir = root / "00_System" / "runtime" / "reports" / "video_learning"
            cards_dir = root / "10_Knowledge" / "candidates" / "learning_cards"
            data_dir.mkdir(parents=True)
            output_dir.mkdir(parents=True)
            (cards_dir / "deep_cards").mkdir(parents=True)
            (output_dir / "latest_scan_report.md").write_text("existing scan", encoding="utf-8")
            (output_dir / "latest_direction_rankings.json").write_text('{"existing": true}', encoding="utf-8")
            (cards_dir / "deep_cards" / "old.md").write_text("old card", encoding="utf-8")
            rows = [
                {
                    "aweme_id": "a1",
                    "title": "#赚钱 普通人做自媒体",
                    "desc": "创业 方法 短视频",
                    "nickname": "作者",
                    "liked_count": "100",
                    "collected_count": "100",
                    "comment_count": "30",
                    "share_count": "40",
                    "aweme_url": "https://example.com/a1",
                    "video_download_url": "https://example.com/a1.mp4",
                },
                {
                    "aweme_id": "a2",
                    "title": "#自媒体 第二条",
                    "desc": "创业 方法 短视频",
                    "nickname": "作者",
                    "liked_count": "90",
                    "collected_count": "90",
                    "comment_count": "20",
                    "share_count": "30",
                    "aweme_url": "https://example.com/a2",
                    "video_download_url": "https://example.com/a2.mp4",
                },
            ]
            (data_dir / "creator_contents_test.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

            calls = []
            original = video_learning.video_status

            def fake_video_status(root_path, record, analyze_video):
                calls.append((record.source_id, analyze_video))
                return {
                    "requested": analyze_video,
                    "has_video_url": bool(record.video_download_url),
                    "ffmpeg": "",
                    "faster_whisper": False,
                    "scenedetect": False,
                    "status": "degraded_video_failed",
                    "artifacts": {},
                    "errors": ["download failed"],
                }

            try:
                video_learning.video_status = fake_video_status
                result = video_learning.run_selected_deep_learning(root, source_ids={"a1"}, analyze_video=True, video_limit=10)
            finally:
                video_learning.video_status = original

            selected_cards = list((cards_dir / "selected_deep_cards").glob("douyin_a1.md"))
            self.assertEqual(calls, [("a1", True)])
            self.assertEqual(len(selected_cards), 1)
            self.assertFalse((cards_dir / "selected_deep_cards" / "douyin_a2.md").exists())
            self.assertEqual((output_dir / "latest_scan_report.md").read_text(encoding="utf-8"), "existing scan")
            self.assertEqual((output_dir / "latest_direction_rankings.json").read_text(encoding="utf-8"), '{"existing": true}')
            self.assertEqual((cards_dir / "deep_cards" / "old.md").read_text(encoding="utf-8"), "old card")
            self.assertEqual(result["requested"], 1)
            self.assertEqual(result["learned"], 1)

    def test_selected_learning_skips_completed_items_unless_forced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "数据" / "douyin" / "json" / "作者"
            data_dir.mkdir(parents=True)
            rows = [
                {
                    "aweme_id": "a1",
                    "title": "#赚钱 普通人做自媒体",
                    "desc": "创业 方法 短视频",
                    "nickname": "作者",
                    "liked_count": "100",
                    "collected_count": "100",
                    "comment_count": "30",
                    "share_count": "40",
                    "aweme_url": "https://example.com/a1",
                    "video_download_url": "https://example.com/a1.mp4",
                }
            ]
            (data_dir / "creator_contents_test.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            state_dir = root / "00_System" / "runtime" / "state" / "video_learning"
            state_dir.mkdir(parents=True)
            (state_dir / "learning_manifest.json").write_text(
                json.dumps(
                    {
                        "items": {
                            "douyin:a1": {
                                "status": "completed",
                                "card_path": "10_Knowledge/candidates/learning_cards/selected_deep_cards/douyin_a1.md",
                            }
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            calls = []
            original = video_learning.video_status

            def fake_video_status(root_path, record, analyze_video):
                calls.append(record.source_id)
                return {
                    "requested": analyze_video,
                    "has_video_url": bool(record.video_download_url),
                    "ffmpeg": "",
                    "faster_whisper": False,
                    "scenedetect": False,
                    "status": "degraded_video_failed",
                    "artifacts": {},
                    "errors": [],
                }

            try:
                video_learning.video_status = fake_video_status
                skipped = video_learning.run_selected_deep_learning(root, source_ids={"a1"}, analyze_video=True)
                forced = video_learning.run_selected_deep_learning(root, source_ids={"a1"}, analyze_video=True, force=True)
            finally:
                video_learning.video_status = original

            self.assertEqual(skipped["skipped"], 1)
            self.assertEqual(skipped["learned"], 0)
            self.assertEqual(forced["learned"], 1)
            self.assertEqual(calls, ["a1"])

    def test_video_status_reuses_existing_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "00_System" / "runtime" / "cache" / "video_learning" / "video_artifacts" / "douyin_a1"
            artifact_dir.mkdir(parents=True)
            for name in ["source.mp4", "audio.wav", "ffprobe.json", "transcript.json", "transcript.srt", "source-Scenes.csv"]:
                (artifact_dir / name).write_text("x", encoding="utf-8")
            (artifact_dir / "transcript.json").write_text(
                json.dumps({"segments": [{"start": 90.0, "end": 99.0, "text": "complete"}]}),
                encoding="utf-8",
            )
            record = video_learning.NormalizedRecord(
                platform="douyin",
                source_id="a1",
                source_file="douyin.json",
                title="标题",
                body="内容",
                author_name="作者",
                published_at="",
                metrics={"likes": 1, "collects": 1, "comments": 1, "shares": 1},
                tags=[],
                url="",
                video_download_url="https://example.com/a1.mp4",
                text_fingerprint="fp",
            )

            with patch("tools.video_learning.media_file_is_usable", return_value=True), patch(
                "tools.video_learning.media_duration_seconds", return_value=100.0
            ):
                status = video_learning.video_status(root, record, analyze_video=False)

            self.assertEqual(status["status"], "video_transcribed_and_scenes_detected")
            self.assertIn("transcript_json", status["artifacts"])
            self.assertIn("scenes_csv", status["artifacts"])

    def test_srt_formatting(self):
        segments = [
            {"index": 1, "start": 0.0, "end": 1.25, "text": "你好"},
            {"index": 2, "start": 61.5, "end": 62.0, "text": "继续"},
        ]

        srt = video_learning.srt_from_segments(segments)

        self.assertIn("00:00:00,000 --> 00:00:01,250", srt)
        self.assertIn("00:01:01,500 --> 00:01:02,000", srt)
        self.assertIn("你好", srt)

    def test_find_executable_checks_homebrew_path(self):
        found = video_learning.find_executable("ffmpeg")
        self.assertTrue(found == "" or found.endswith("ffmpeg"))


if __name__ == "__main__":
    unittest.main()
