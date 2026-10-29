import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'auth_service.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';
import 'api.dart';
import 'discover.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  var ready = false;
  try {
    const key = String.fromEnvironment('FIREBASE_API_KEY');
    if (key.isNotEmpty) {
      await Firebase.initializeApp(
        options: const FirebaseOptions(
          apiKey: key,
          appId: String.fromEnvironment('FIREBASE_APP_ID'),
          messagingSenderId: String.fromEnvironment('FIREBASE_SENDER_ID'),
          projectId: String.fromEnvironment('FIREBASE_PROJECT_ID'),
        ),
      );
    } else {
      await Firebase.initializeApp();
    }
    ready = true;
  } catch (_) {
    /* Public reading remains available when account configuration is absent. */
  }
  runApp(WeAwareApp(api: Api(authReady: ready)));
}

final appearance = ValueNotifier<ThemeMode>(ThemeMode.system);
final GlobalKey<NavigatorState> appNavigatorKey = GlobalKey<NavigatorState>();
const _shareLinkMethods = MethodChannel('weaware/shared_links/methods');
const _shareLinkEvents = EventChannel('weaware/shared_links/events');
const _siteOrigin = 'https://weaware-3504c.web.app';

class WeAwareApp extends StatefulWidget {
  const WeAwareApp({super.key, required this.api});
  final Api api;

  @override
  State<WeAwareApp> createState() => _WeAwareAppState();
}

class _WeAwareAppState extends State<WeAwareApp> {
  StreamSubscription<dynamic>? _sharedLinks;
  final Set<String> _openedSharedStories = {};

  @override
  void initState() {
    super.initState();
    _sharedLinks = _shareLinkEvents.receiveBroadcastStream().listen(_openSharedStory);
    _shareLinkMethods.invokeMethod<String>('initialUri').then((uri) {
      if (uri != null) WidgetsBinding.instance.addPostFrameCallback((_) => _openSharedStory(uri));
    }).catchError((_) {});
  }

  @override
  void dispose() {
    _sharedLinks?.cancel();
    super.dispose();
  }

  void _openSharedStory(dynamic value) {
    final uri = Uri.tryParse(value?.toString() ?? '');
    if (uri == null || uri.scheme != 'https' || uri.host != 'weaware-3504c.web.app' || uri.pathSegments.length != 2 || uri.pathSegments.first != 's') return;
    final id = uri.pathSegments[1];
    if (id.isEmpty || !_openedSharedStories.add(id)) return;
    final navigator = appNavigatorKey.currentState;
    if (navigator == null) {
      _openedSharedStories.remove(id);
      WidgetsBinding.instance.addPostFrameCallback((_) => _openSharedStory(value));
      return;
    }
    navigator.push(MaterialPageRoute<void>(builder: (_) => SharedArticleRoute(api: widget.api, articleId: id))).whenComplete(() => _openedSharedStories.remove(id));
  }

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<ThemeMode>(
    valueListenable: appearance,
    builder: (context, mode, _) => MaterialApp(
      title: 'WeAware',
      themeMode: mode,
      darkTheme: readingTheme(Brightness.dark),
      debugShowCheckedModeBanner: false,
      theme: readingTheme(Brightness.light),
      navigatorKey: appNavigatorKey,
      home: Home(api: widget.api),
    ),
  );
}

class SharedArticleRoute extends StatefulWidget {
  const SharedArticleRoute({super.key, required this.api, required this.articleId});
  final Api api;
  final String articleId;

  @override
  State<SharedArticleRoute> createState() => _SharedArticleRouteState();
}

class _SharedArticleRouteState extends State<SharedArticleRoute> {
  Json? article;
  String error = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => error = '');
    try {
      final result = await widget.api.call('/articles/${Uri.encodeComponent(widget.articleId)}');
      if (mounted) setState(() => article = result);
    } catch (_) {
      if (mounted) setState(() => error = 'This story is unavailable. Check the link or try again.');
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Shared story')),
    body: article != null
      ? Reader(api: widget.api, article: article!, fetchFullArticle: false)
      : error.isNotEmpty
        ? Center(child: Padding(padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, children: [Text(error), const SizedBox(height: 16), FilledButton(onPressed: _load, child: const Text('Try again'))])))
        : const Center(child: CircularProgressIndicator()),
  );
}

void notice(BuildContext c, Object e) => ScaffoldMessenger.of(c).showSnackBar(
  SnackBar(content: Text(e.toString().replaceFirst('Exception: ', ''))),
);
String publicationLabel(BuildContext context, dynamic value) {
  final date = DateTime.tryParse(value?.toString() ?? '')?.toLocal();
  if (date == null) return 'Recently published';
  final labels = MaterialLocalizations.of(context);
  return '${labels.formatMediumDate(date)} · ${labels.formatTimeOfDay(TimeOfDay.fromDateTime(date))}';
}

Future<void> openLink(String value) async {
  final uri = Uri.tryParse(value);
  if (uri == null || !['https', 'http'].contains(uri.scheme)) {
    throw Exception('This source link is unavailable.');
  }
  if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
    throw Exception('Could not open this link.');
  }
}

List<Json> objects(dynamic value) => (value is List ? value : [])
    .whereType<Map>()
    .map((e) => Map<String, dynamic>.from(e))
    .toList();
List<String> strings(dynamic value) =>
    (value is List ? value : []).map((e) => e.toString()).toList();
Widget heading(String text) => Padding(
  padding: const EdgeInsets.symmetric(vertical: 12),
  child: Text(
    text,
    style: const TextStyle(
      fontFamily: 'serif',
      fontSize: 30,
      fontWeight: FontWeight.bold,
    ),
  ),
);
Widget copy(String text) => Padding(
  padding: const EdgeInsets.only(bottom: 16),
  child: Text(text, style: const TextStyle(fontSize: 16, height: 1.6)),
);

class Home extends StatefulWidget {
  const Home({super.key, required this.api});
  final Api api;
  @override
  State<Home> createState() => _HomeState();
}

class _HomeState extends State<Home> {
  int tab = 0;
  bool discoverOpened = false;
  StreamSubscription<User?>? auth;
  @override
  void initState() {
    super.initState();
    if (widget.api.authReady) {
      auth = widget.api.accountAuth!.userChanges().listen((_) {
        audioDesk.close();
        if (mounted) setState(() {});
      });
    }
  }

  @override
  void dispose() {
    auth?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final api = widget.api;
    return Scaffold(
      appBar: AppBar(
        title: Text(
          [
            'Today’s edition',
            'Discover',
            'Listen',
            'Crosscheck',
            'Sherlock',
          ][tab],
        ),
        actions: [
          PopupMenuButton<ThemeMode>(
            tooltip: "Appearance",
            icon: const Icon(Icons.brightness_6_outlined),
            onSelected: (mode) => appearance.value = mode,
            itemBuilder: (_) => const [
              PopupMenuItem(
                value: ThemeMode.system,
                child: Text("System appearance"),
              ),
              PopupMenuItem(value: ThemeMode.light, child: Text("Light")),
              PopupMenuItem(value: ThemeMode.dark, child: Text("Dark")),
            ],
          ),
          IconButton(
            tooltip: 'Your account',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => Account(api: api)),
            ),
            icon: Icon(
              api.user == null ? Icons.person_outline : Icons.account_circle,
            ),
          ),
        ],
      ),
      body: IndexedStack(
        index: tab,
        children: [
          Feed(api: api),
          if (discoverOpened)
            Discover(
              key: ValueKey('discover-${api.user?.uid ?? 'guest'}'),
              api: api,
              onOpen: (article) => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => Reader(api: api, article: article),
                ),
              ),
              onSignIn: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => Account(api: api)),
              ),
            )
          else
            const SizedBox.shrink(),
          Podcasts(api: api),
          Newsletter(key: ValueKey("newsletter-${api.user?.uid}"), api: api),
          Research(key: ValueKey("research-${api.user?.uid}"), api: api),
        ],
      ),
      bottomNavigationBar: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const AudioControls(compact: true),
          NavigationBar(
            selectedIndex: tab,
            onDestinationSelected: (i) => setState(() {
              tab = i;
              if (i == 1) discoverOpened = true;
            }),
            destinations: const [
              NavigationDestination(icon: Icon(Icons.newspaper), label: 'News'),
              NavigationDestination(
                icon: Icon(Icons.swipe_outlined),
                label: 'Discover',
              ),
              NavigationDestination(
                icon: Icon(Icons.headphones),
                label: 'Listen',
              ),
              NavigationDestination(
                icon: Icon(Icons.mail_outline),
                label: 'Crosscheck',
              ),
              NavigationDestination(
                icon: Icon(Icons.travel_explore),
                label: 'Sherlock',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class Feed extends StatefulWidget {
  const Feed({super.key, required this.api});
  final Api api;
  @override
  State<Feed> createState() => _FeedState();
}

class _FeedState extends State<Feed> {
  List<Json> articles = [];
  List<String> topics = [];
  String topic = 'All', query = '';
  int total = 0, generation = 0;
  bool busy = false;
  String? error;
  final search = TextEditingController();
  @override
  void initState() {
    super.initState();
    load();
    widget.api
        .call('/topics')
        .then((r) {
          if (mounted) setState(() => topics = strings(r['topics']));
        })
        .catchError((_) {});
  }

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Future<void> load({bool more = false}) async {
    final current = ++generation;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final params = Uri(
        queryParameters: {
          'limit': widget.api.user == null ? '9' : '24',
          'offset': more ? '${articles.length}' : '0',
          if (topic != 'All') 'topic': topic,
          if (query.isNotEmpty) 'q': query,
        },
      ).query;
      final r = await widget.api.call('/articles?$params');
      if (mounted && current == generation) {
        setState(() {
          articles = [if (more) ...articles, ...objects(r['articles'])];
          total = r['total'] as int? ?? articles.length;
          audioDesk.articles = articles
              .take(widget.api.user == null ? 3 : articles.length)
              .toList();
        });
      }
    } catch (e) {
      if (mounted && current == generation) {
        setState(() => error = e.toString());
      }
    } finally {
      if (mounted && current == generation) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: load,
    child: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const Text(
          'THE INDEPENDENT READING ROOM',
          style: TextStyle(fontSize: 10, letterSpacing: 1.7),
        ),
        heading('WeAware'),
        Text(
          'Many sources. A clearer picture.',
          style: TextStyle(
            fontFamily: 'serif',
            fontSize: 17,
            height: 1.5,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        Divider(color: Theme.of(context).colorScheme.onSurface, thickness: 2),
        const SizedBox(height: 8),
        TextField(
          controller: search,
          maxLength: 200,
          decoration: InputDecoration(
            hintText: 'Search reporting',
            prefixIcon: const Icon(Icons.search),
            counterText: '',
            suffixIcon: IconButton(
              tooltip: 'Search',
              onPressed: () {
                query = search.text.trim();
                load();
              },
              icon: const Icon(Icons.arrow_forward),
            ),
          ),
          textInputAction: TextInputAction.search,
          onSubmitted: (v) {
            query = v.trim();
            load();
          },
        ),
        const SizedBox(height: 16),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: ['All', ...topics]
                .map(
                  (t) => Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(t),
                      selected: topic == t,
                      onSelected: (_) {
                        topic = t;
                        load();
                      },
                    ),
                  ),
                )
                .toList(),
          ),
        ),
        if (busy) const LinearProgressIndicator(),
        if (error != null) ...[
          copy(error!),
          TextButton(onPressed: load, child: const Text('Retry')),
        ],
        if (!busy && articles.isEmpty && error == null)
          copy('No stories found. Try another topic or search.'),
        ...articles
            .take(widget.api.user == null ? 9 : articles.length)
            .toList()
            .asMap()
            .entries
            .map((entry) {
              final a = entry.value;
              final locked = widget.api.user == null && entry.key >= 3;
              return Card(
                shape: const RoundedRectangleBorder(),
                margin: const EdgeInsets.only(top: 22),
                child: InkWell(
                  borderRadius: BorderRadius.circular(12),
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => locked
                          ? Account(api: widget.api)
                          : Reader(api: widget.api, article: a),
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 22),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (a['image'] is String)
                          ClipRRect(
                            borderRadius: BorderRadius.circular(8),
                            child: Image.network(
                              a['image'],
                              height: 190,
                              width: double.infinity,
                              fit: BoxFit.cover,
                              errorBuilder: (_, _, _) =>
                                  const SizedBox.shrink(),
                            ),
                          ),
                        const SizedBox(height: 12),
                        Text(
                          "${a['topic']} · ${a['readMins']} min read"
                              .toUpperCase(),
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.onSurface,
                            fontSize: 11,
                            letterSpacing: 1,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        Text(
                          a['title'] ?? '',
                          style: const TextStyle(
                            fontFamily: 'serif',
                            fontSize: 23,
                            height: 1.2,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          locked
                              ? 'Sign in to unlock the full news feed.'
                              : a['summary'] ?? '',
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 14,
                            height: 1.5,
                            color: Theme.of(
                              context,
                            ).colorScheme.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Text(
                          locked
                              ? '🔒 Sign in to read'
                              : '${objects(a['sources']).length} sources · ${a['consensus']}% agreement',
                          style: TextStyle(
                            fontSize: 12,
                            color: Theme.of(
                              context,
                            ).colorScheme.onSurfaceVariant,
                          ),
                        ),
                        const Divider(height: 1),
                      ],
                    ),
                  ),
                ),
              );
            }),
        if (widget.api.user == null)
          FilledButton(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => Account(api: widget.api)),
            ),
            child: const Text('Sign in for the full feed'),
          ),
        if (widget.api.user != null && articles.length < total)
          OutlinedButton(
            onPressed: busy ? null : () => load(more: true),
            child: const Text('Load more stories'),
          ),
        const SizedBox(height: 20),
        copy(
          'AI-assisted summaries and automated signals are reading aids. They do not establish truth. Open the original reporting for important claims.',
        ),
      ],
    ),
  );
}

class Reader extends StatefulWidget {
  const Reader({super.key, required this.api, required this.article, this.fetchFullArticle = true});
  final Api api;
  final Json article;
  final bool fetchFullArticle;
  @override
  State<Reader> createState() => _ReaderState();
}

class _ReaderState extends State<Reader> {
  late Json article = widget.article;
  @override
  void initState() {
    super.initState();
    if (!widget.fetchFullArticle) return;
    widget.api
        .call('/articles/${Uri.encodeComponent(article['id'])}')
        .then((v) {
          if (mounted) setState(() => article = v);
        })
        .catchError((e) {
          if (mounted) notice(context, e);
        });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(article['topic'] ?? 'Story'),
      actions: [
        IconButton(
          tooltip: 'Share story',
          onPressed: () => SharePlus.instance.share(
            ShareParams(
              text:
                  '${article['title']}\n$_siteOrigin/s/${Uri.encodeComponent(article['id'])}',
            ),
          ),
          icon: const Icon(Icons.ios_share),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(22),
      children: [
        Text(
          '${publicationLabel(context, article['publishedAt'])} · ${article['readMins']} min read',
        ),
        heading(article['title'] ?? ''),
        copy(article['summary'] ?? ''),
        if (article['image'] is String)
          Image.network(
            article['image'],
            errorBuilder: (_, _, _) => const SizedBox.shrink(),
          ),
        AudioPanel(
          api: widget.api,
          articleId: article['id'],
          title: article['title'],
        ),
        ...strings(article['body']).map(copy),
        heading('Source notes'),
        copy(
          '${article['consensus']}% source agreement. Agreement is an automated signal, not a guarantee of accuracy.',
        ),
        ...objects(article['sources']).map(
          (s) => Card(
            child: ListTile(
              isThreeLine: true,
              title: Text(s['outlet'] ?? 'Source'),
              subtitle: Text(
                '${s['stance'] == 'agree'
                    ? 'Corroborates'
                    : s['stance'] == 'context'
                    ? 'Adds context'
                    : 'Disputes'}\n${s['note'] ?? ''}',
              ),
              trailing: const Icon(Icons.open_in_new),
              onTap: s['url'] is String
                  ? () async {
                      try {
                        await openLink(s['url']);
                      } catch (e) {
                        if (context.mounted) notice(context, e);
                      }
                    }
                  : null,
            ),
          ),
        ),
        heading('Claims to inspect'),
        if (objects(article['flaggedClaims']).isEmpty)
          copy('No low-confidence claims flagged in this story.'),
        ...objects(article['flaggedClaims']).map(
          (f) => Card(
            child: ListTile(
              leading: const Icon(Icons.info_outline),
              title: Text(f['claim'] ?? ''),
              subtitle: Text(f['reason'] ?? ''),
            ),
          ),
        ),
        copy(
          'WeAware uses AI to help cluster, draft and summarize coverage. Read the linked sources and check important claims.',
        ),
      ],
    ),
  );
}

final audioDesk = AudioDesk();

class AudioDesk extends ChangeNotifier {
  final player = AudioPlayer();
  List<Json> articles = [], episodes = [], queue = [];
  Json? current;
  Api? api;
  bool articleMode = true, loading = false;
  String? error;
  double speed = 1;
  int operation = 0;
  bool completedHandled = false;
  AudioDesk() {
    player.playerStateStream.listen((state) {
      notifyListeners();
      if (state.processingState == ProcessingState.completed &&
          !completedHandled) {
        completedHandled = true;
        if (index >= 0 && index < queue.length - 1) {
          Future.microtask(() => skip(1));
        }
      }
    });
  }
  Future<void> select(Api api, Json item, bool isArticle) async {
    completedHandled = false;
    this.api = api;
    articleMode = isArticle;
    current = item;
    queue = List<Json>.from(
      isArticle ? (api.user == null ? articles.take(3) : articles) : episodes,
    );
    final run = ++operation;
    loading = true;
    error = null;
    notifyListeners();
    await player.stop();
    try {
      String? url = item['audioUrl'] as String?;
      if (isArticle) {
        final path = '/articles/${Uri.encodeComponent(item['id'])}/audio';
        var result = await api.call(path, method: 'POST');
        for (
          var i = 0;
          result['status'] != 'ready' && result['status'] != 'failed' && i < 90;
          i++
        ) {
          await Future<void>.delayed(const Duration(seconds: 2));
          if (run != operation) return;
          result = await api.call(path);
        }
        if (run != operation) return;
        if (result['status'] != 'ready') {
          throw Exception(
            result['error'] ?? 'Audio is still preparing. Try again shortly.',
          );
        }
        url = result['audioUrl'] as String?;
      }
      if (url == null) throw Exception('Audio is unavailable.');
      if (run != operation) return;
      await player.setUrl(url);
      await player.setSpeed(speed);
      if (run != operation) return;
      unawaited(
        player.play().catchError((Object e) {
          error = 'Playback failed. Retry to refresh the audio link.';
          notifyListeners();
        }),
      );
    } catch (e) {
      if (run == operation) error = e.toString();
    } finally {
      if (run == operation) {
        loading = false;
        notifyListeners();
      }
    }
  }

  int get index => queue.indexWhere((e) => e['id'] == current?['id']);
  void skip(int delta) {
    final next = index + delta;
    if (next >= 0 && next < queue.length && api != null) {
      select(api!, queue[next], articleMode);
    }
  }

  void changeSpeed() {
    speed = speed == 1
        ? 1.25
        : speed == 1.25
        ? 1.5
        : 1;
    player.setSpeed(speed);
    notifyListeners();
  }

  void seek(int seconds) => player.seek(
    Duration(
      milliseconds: (player.position.inMilliseconds + seconds * 1000).clamp(
        0,
        player.duration?.inMilliseconds ?? 0,
      ),
    ),
  );
  void toggle() {
    if (player.playing) {
      player.pause();
    } else {
      if (player.processingState == ProcessingState.completed) {
        player.seek(Duration.zero);
      }
      player.play();
    }
  }

  void close() {
    operation++;
    player.stop();
    current = null;
    loading = false;
    notifyListeners();
  }
}

class AudioControls extends StatelessWidget {
  const AudioControls({super.key, this.compact = false});
  final bool compact;
  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: audioDesk,
    builder: (context, _) {
      final desk = audioDesk;
      if (desk.current == null) return const SizedBox.shrink();
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '${desk.loading ? 'Preparing AI audio…' : 'AI narration'} · ${desk.current!['title']}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                IconButton(
                  tooltip: 'Close player',
                  onPressed: desk.close,
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            if (desk.error != null) Text(desk.error!),
            if (desk.loading)
              const LinearProgressIndicator()
            else
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  IconButton(
                    tooltip: 'Previous story',
                    onPressed: desk.index > 0 ? () => desk.skip(-1) : null,
                    icon: const Icon(Icons.skip_previous),
                  ),
                  IconButton(
                    tooltip: 'Back 15 seconds',
                    onPressed: () => desk.seek(-15),
                    icon: const Icon(Icons.replay),
                  ),
                  IconButton(
                    tooltip: desk.player.playing ? 'Pause' : 'Play',
                    onPressed: desk.error == null
                        ? desk.toggle
                        : () => desk.select(
                            desk.api!,
                            desk.current!,
                            desk.articleMode,
                          ),
                    icon: Icon(
                      desk.player.playing
                          ? Icons.pause_circle_filled
                          : Icons.play_circle_fill,
                      size: 36,
                    ),
                  ),
                  IconButton(
                    tooltip: 'Forward 15 seconds',
                    onPressed: () => desk.seek(15),
                    icon: const Icon(Icons.forward_10),
                  ),
                  IconButton(
                    tooltip: 'Next story',
                    onPressed:
                        desk.index >= 0 && desk.index < desk.queue.length - 1
                        ? () => desk.skip(1)
                        : null,
                    icon: const Icon(Icons.skip_next),
                  ),
                  TextButton(
                    onPressed: () {
                      desk.changeSpeed();
                    },
                    child: Text('${desk.speed}x'),
                  ),
                ],
              ),
            if (!compact)
              StreamBuilder<Duration>(
                stream: desk.player.positionStream,
                builder: (_, snapshot) {
                  final end = (desk.player.duration?.inMilliseconds ?? 1).clamp(
                    1,
                    1 << 40,
                  );
                  return Slider(
                    value: (snapshot.data?.inMilliseconds ?? 0)
                        .clamp(0, end)
                        .toDouble(),
                    max: end.toDouble(),
                    onChanged: (v) =>
                        desk.player.seek(Duration(milliseconds: v.toInt())),
                  );
                },
              ),
            if (!compact && desk.queue.isNotEmpty)
              ExpansionTile(
                title: Text('Listening queue · ${desk.queue.length}'),
                children: desk.queue
                    .map(
                      (item) => ListTile(
                        title: Text(item['title'] ?? ''),
                        selected: item['id'] == desk.current?['id'],
                        onTap: () =>
                            desk.select(desk.api!, item, desk.articleMode),
                      ),
                    )
                    .toList(),
              ),
          ],
        ),
      );
    },
  );
}

class AudioPanel extends StatelessWidget {
  const AudioPanel({
    super.key,
    required this.api,
    required this.title,
    this.articleId,
    this.url,
  });
  final Api api;
  final String title;
  final String? articleId, url;
  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: audioDesk,
    builder: (context, _) {
      final active = audioDesk.current?['id'] == (articleId ?? url);
      return Card(
        child: active
            ? const AudioControls()
            : TextButton.icon(
                onPressed: () => audioDesk.select(api, {
                  'id': articleId ?? url,
                  'title': title,
                  if (url != null) 'audioUrl': url,
                }, articleId != null),
                icon: const Icon(Icons.headphones),
                label: Text('Listen · $title'),
              ),
      );
    },
  );
}

class Account extends StatefulWidget {
  const Account({super.key, required this.api});
  final Api api;
  @override
  State<Account> createState() => _AccountState();
}

class _AccountState extends State<Account> {
  final email = TextEditingController(), password = TextEditingController();
  bool busy = false, register = false;
  String message = '';
  StreamSubscription<User?>? subscription;
  String? owner;
  @override
  void initState() {
    super.initState();
    owner = widget.api.user?.uid;
    subscription = widget.api.accountAuth?.userChanges().listen((user) {
      if (!mounted) return;
      setState(() {
        if (user?.uid != owner) {
          owner = user?.uid;
          register = false;
          password.clear();
          message = '';
        }
      });
    });
  }

  @override
  void dispose() {
    subscription?.cancel();
    email.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> act(Future<String?> Function() action) async {
    if (busy) return;
    setState(() {
      busy = true;
      message = '';
    });
    try {
      final result = await action();
      if (mounted) {
        setState(() {
          message = result ?? '';
          if (widget.api.user != null) {
            register = false;
            password.clear();
          }
        });
      }
    } catch (error) {
      if (mounted) setState(() => message = accountError(error));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = widget.api.user;
    final auth = widget.api.accountAuth;
    return Scaffold(
      appBar: AppBar(title: const Text('Your account')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          heading(
            user != null
                ? 'Signed in'
                : register
                ? 'Create your WeAware account'
                : 'Sign in to WeAware',
          ),
          if (!widget.api.authReady)
            copy(
              'Account sign-in needs this Android app’s Firebase configuration. Public news and podcasts are available. See the setup guide to connect Firebase.',
            ),
          if (user != null) ...[
            copy(user.email ?? 'Signed in'),
            copy(
              user.emailVerified
                  ? 'Email verified'
                  : 'Verify your email before subscribing or requesting research.',
            ),
            if (!user.emailVerified)
              OutlinedButton(
                onPressed: busy
                    ? null
                    : () => act(() async {
                        await auth!.verifyEmail();
                        return 'Verification email sent.';
                      }),
                child: const Text('Send verification email'),
              ),
            OutlinedButton(
              onPressed: busy
                  ? null
                  : () => act(() async {
                      await auth!.refresh();
                      return 'Account refreshed.';
                    }),
              child: const Text('Refresh verification'),
            ),
            FilledButton(
              onPressed: busy
                  ? null
                  : () => act(() async {
                      await auth!.signOut();
                      return null;
                    }),
              child: const Text('Sign out'),
            ),
            OutlinedButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => Editorial(api: widget.api)),
              ),
              child: const Text('Podcast editorial desk'),
            ),
          ] else ...[
            TextField(
              key: const Key('auth.email'),
              controller: email,
              keyboardType: TextInputType.emailAddress,
              textCapitalization: TextCapitalization.none,
              autocorrect: false,
              autofillHints: const [AutofillHints.email],
              decoration: const InputDecoration(labelText: 'Email'),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('auth.password'),
              controller: password,
              obscureText: true,
              autofillHints: [
                register ? AutofillHints.newPassword : AutofillHints.password,
              ],
              decoration: const InputDecoration(labelText: 'Password'),
            ),
            const SizedBox(height: 16),
            FilledButton(
              key: const Key('auth.submit'),
              onPressed: !widget.api.authReady || busy
                  ? null
                  : () => act(() async {
                      final address = email.text.trim();
                      final secret = password.text;
                      if (address.isEmpty || secret.isEmpty) {
                        throw Exception('Enter your email and password.');
                      }
                      if (register) return auth!.createAccount(address, secret);
                      await auth!.signIn(address, secret);
                      return null;
                    }),
              child: Text(register ? 'Create account' : 'Sign in'),
            ),
            TextButton(
              key: const Key('auth.mode'),
              onPressed: busy
                  ? null
                  : () => setState(() {
                      register = !register;
                      message = '';
                      password.clear();
                    }),
              child: Text(
                register
                    ? 'Already have an account? Sign in'
                    : 'New here? Create account',
              ),
            ),
            OutlinedButton.icon(
              key: const Key('auth.google'),
              onPressed: !widget.api.authReady || busy
                  ? null
                  : () => act(() async {
                      await auth!.google();
                      return null;
                    }),
              icon: const Icon(Icons.login),
              label: const Text('Continue with Google'),
            ),
            TextButton(
              onPressed: !widget.api.authReady || busy
                  ? null
                  : () => act(() async {
                      if (email.text.trim().isEmpty) {
                        throw Exception('Enter your email first.');
                      }
                      await auth!.resetPassword(email.text.trim());
                      return 'Password reset email requested. Check your inbox.';
                    }),
              child: const Text('Reset password'),
            ),
          ],
          if (busy) const LinearProgressIndicator(),
          if (message.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(
                message,
                key: const Key('auth.message'),
                semanticsLabel: message,
              ),
            ),
          const Divider(height: 40),
          heading('About WeAware'),
          copy(
            'Multi-source news, original reporting and room for uncertainty. WeAware uses AI to help cluster coverage, draft summaries and synthesize narration. Editorial review does not replace your judgment; follow the sources for important claims.',
          ),
          TextButton(
            onPressed: () => openLink(_siteOrigin),
            child: const Text('Visit WeAware'),
          ),
        ],
      ),
    );
  }
}

class Podcasts extends StatefulWidget {
  const Podcasts({super.key, required this.api});
  final Api api;
  @override
  State<Podcasts> createState() => _PodcastsState();
}

class _PodcastsState extends State<Podcasts> {
  final Set<String> liked = {};
  List<Json> episodes = [];
  String? error;
  bool busy = true;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = await widget.api.call('/podcasts/episodes');
      if (mounted) {
        setState(() {
          episodes = objects(result['episodes']);
          audioDesk.episodes = episodes
              .map((e) => {...e, 'id': e['audioUrl'] ?? e['id']})
              .toList();
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: load,
    child: ListView(
      padding: const EdgeInsets.all(22),
      children: [
        heading('Listen beyond\nthe headline.'),
        copy(
          'Published briefings, AI narration, editorial review and sources included.',
        ),
        OutlinedButton.icon(
          onPressed: () async {
            await Clipboard.setData(
              const ClipboardData(text: '$apiBase/podcasts/feed.xml'),
            );
            if (context.mounted) {
              notice(
                context,
                'RSS feed copied. Paste it into your podcast app.',
              );
            }
          },
          icon: const Icon(Icons.rss_feed),
          label: const Text('Copy podcast RSS feed'),
        ),
        if (busy) const LinearProgressIndicator(),
        if (error != null) ...[
          copy(error!),
          TextButton(onPressed: load, child: const Text('Retry')),
        ],
        if (!busy && error == null && episodes.isEmpty)
          copy(
            'No published episodes yet. New briefings appear after editorial review.',
          ),
        ...episodes.map(
          (e) => Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(child: Text(e['topic'] ?? 'WeAware briefing')),
                      IconButton(
                        tooltip: liked.contains(e['id'])
                            ? 'Unlike episode'
                            : 'Like episode',
                        onPressed: () => setState(() {
                          final id = e['id'].toString();
                          if (liked.contains(id)) {
                            liked.remove(id);
                          } else {
                            liked.add(id);
                          }
                        }),
                        icon: Icon(
                          liked.contains(e['id'])
                              ? Icons.favorite
                              : Icons.favorite_border,
                        ),
                      ),
                    ],
                  ),
                  heading(e['title'] ?? 'Briefing'),
                  copy(e['description'] ?? ''),
                  if (e['audioUrl'] is String)
                    AudioPanel(
                      key: ValueKey(e['id']),
                      api: widget.api,
                      title: e['title'] ?? 'briefing',
                      url: e['audioUrl'],
                    ),
                  if (e['script'] is String)
                    ExpansionTile(
                      title: const Text('Read transcript'),
                      children: [copy(e['script'])],
                    ),
                  ...objects(e['sources']).map(
                    (s) => ListTile(
                      title: Text(s['outlet'] ?? s['title'] ?? 'Source'),
                      onTap: s['url'] is String
                          ? () => openLink(s['url'])
                          : null,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    ),
  );
}

class Newsletter extends StatefulWidget {
  const Newsletter({super.key, required this.api});
  final Api api;
  @override
  State<Newsletter> createState() => _NewsletterState();
}

class _NewsletterState extends State<Newsletter> {
  List<String> topics = [];
  Set<String> selected = {};
  String cadence = 'weekly';
  bool consent = false, busy = false;
  Json? preferences;
  String? error;
  @override
  void initState() {
    super.initState();
    if (widget.api.user != null) {
      Future.microtask(() => request('GET', '/newsletters/preferences'));
    }
    widget.api
        .call('/topics')
        .then((r) {
          if (mounted) setState(() => topics = strings(r['topics']));
        })
        .catchError((_) {});
  }

  Future<void> request(String method, String path, {Json? body}) async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final r = await widget.api.call(
        path,
        method: method,
        body: body,
        authenticated: true,
      );
      if (mounted) {
        setState(() {
          if (r.containsKey('subscribed')) preferences = r;
          if (r['topics'] is List) selected = strings(r['topics']).toSet();
          if (r['cadence'] is String) cadence = r['cadence'];
        });
        notice(
          context,
          r['message'] ??
              (method == 'GET'
                  ? 'Preferences loaded.'
                  : 'Subscription updated.'),
        );
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(22),
    children: [
      heading('The Crosscheck'),
      copy(
        'Your briefing, tuned to you. Choose topics and a daily or weekly email, with original sources and disagreements kept in.',
      ),
      if (widget.api.user == null) ...[
        copy('Sign in and verify your email to manage delivery.'),
        FilledButton(
          onPressed: () => Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => Account(api: widget.api)),
          ),
          child: const Text('Sign in'),
        ),
      ] else ...[
        Text(widget.api.user!.email ?? ''),
        TextButton(
          onPressed: busy
              ? null
              : () => request('GET', '/newsletters/preferences'),
          child: const Text('Load saved preferences'),
        ),
        if (preferences != null)
          copy(
            preferences!['subscribed'] == true
                ? 'Subscribed · Next delivery: ${preferences!['nextDeliveryAt'] ?? 'Scheduled'}'
                : 'Not subscribed',
          ),
        if (preferences?['deliveryReady'] == false)
          copy(
            'Email delivery is not configured yet. You can save preferences for when delivery is enabled.',
          ),
        Wrap(
          spacing: 8,
          children: topics
              .map(
                (t) => FilterChip(
                  label: Text(t),
                  selected: selected.contains(t),
                  onSelected: (v) => setState(() {
                    if (v) {
                      selected.add(t);
                    } else {
                      selected.remove(t);
                    }
                  }),
                ),
              )
              .toList(),
        ),
        const SizedBox(height: 18),
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'daily', label: Text('Daily')),
            ButtonSegment(value: 'weekly', label: Text('Weekly')),
          ],
          selected: {cadence},
          onSelectionChanged: (v) => setState(() => cadence = v.first),
        ),
        CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text(
            'I agree to receive The Crosscheck by email. I can unsubscribe at any time.',
          ),
          value: consent,
          onChanged: (v) => setState(() => consent = v ?? false),
        ),
        FilledButton(
          onPressed: busy || !consent || selected.isEmpty
              ? null
              : () => request(
                  'PUT',
                  '/newsletters/preferences',
                  body: {
                    'topics': selected.toList(),
                    'cadence': cadence,
                    'consent': true,
                  },
                ),
          child: const Text('Save subscription'),
        ),
        OutlinedButton(
          onPressed: busy
              ? null
              : () => request(
                  'POST',
                  '/newsletters/test',
                  body: {'topics': selected.toList(), 'cadence': cadence},
                ),
          child: const Text('Send a test email'),
        ),
        TextButton(
          onPressed: busy
              ? null
              : () => request('POST', '/newsletters/preferences/unsubscribe'),
          child: const Text('Unsubscribe'),
        ),
      ],
      if (busy) const LinearProgressIndicator(),
      if (error != null) copy(error!),
    ],
  );
}

class Research extends StatefulWidget {
  const Research({super.key, required this.api});
  final Api api;
  @override
  State<Research> createState() => _ResearchState();
}

class _ResearchState extends State<Research> {
  final question = TextEditingController(), scope = TextEditingController();
  String length = 'standard';
  Json? access;
  List<Json> history = [];
  bool busy = false;
  String? error, submissionKey, signature;
  Timer? timer;
  @override
  void initState() {
    super.initState();
    if (widget.api.user != null) Future.microtask(load);
    timer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (widget.api.user != null &&
          history.any(
            (r) => [
              'queued',
              'researching',
              'awaiting_review',
            ].contains(r['status']),
          )) {
        load();
      }
    });
  }

  @override
  void dispose() {
    timer?.cancel();
    question.dispose();
    scope.dispose();
    super.dispose();
  }

  Future<void> load() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final a = await widget.api.call(
        '/sherlock/entitlement',
        authenticated: true,
      );
      final h = await widget.api.call(
        '/sherlock/requests',
        authenticated: true,
      );
      if (mounted) {
        setState(() {
          access = a;
          history = objects(h['requests']);
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> submit() async {
    final sig = '${question.text.trim()}|${scope.text.trim()}|$length';
    if (signature != sig) {
      signature = sig;
      submissionKey = 'mobile-${DateTime.now().microsecondsSinceEpoch}';
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.api.call(
        '/sherlock/requests',
        method: 'POST',
        authenticated: true,
        body: {
          'question': question.text.trim(),
          'scope': scope.text.trim(),
          'reportLength': length,
          'submissionKey': submissionKey,
        },
      );
      question.clear();
      scope.clear();
      signature = null;
      if (mounted) {
        notice(
          context,
          'Investigation submitted. Your notebook will show its progress.',
        );
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) {
        setState(() => busy = false);
        if (error == null) await load();
      }
    }
  }

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(22),
    children: [
      const Text('SHERLOCK MODE · THE RESEARCH DESK'),
      heading('Follow the trail.\nQuestion the story.'),
      copy(
        'Ask a specific question. Jeff compares accessible evidence, connects claims to sources, and sends the brief for editorial review. This invite-only pilot uses research credits; failed investigations return the credit.',
      ),
      if (widget.api.user == null)
        FilledButton(
          onPressed: () => Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => Account(api: widget.api)),
          ),
          child: const Text('Sign in to open your notebook'),
        )
      else ...[
        OutlinedButton.icon(
          onPressed: busy ? null : load,
          icon: const Icon(Icons.refresh),
          label: const Text('Refresh notebook & access'),
        ),
        if (access != null) ...[
          copy(
            '${access!['credits'] ?? 0} research credits · ${access!['acceptingRequests'] == true ? 'Desk open' : 'Desk paused'}',
          ),
          if (access!['eligible'] != true)
            copy(
              'Your account does not currently have access to this research pilot.',
            ),
          TextField(
            controller: question,
            minLines: 3,
            maxLines: 5,
            maxLength: 1200,
            decoration: const InputDecoration(
              labelText: 'Your research question',
              helperText: 'At least 20 characters',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: scope,
            minLines: 2,
            maxLines: 4,
            maxLength: 600,
            decoration: const InputDecoration(
              labelText: 'Scope or context (optional)',
            ),
          ),
          DropdownButtonFormField<String>(
            initialValue: length,
            items: const [
              DropdownMenuItem(value: 'brief', child: Text('Brief')),
              DropdownMenuItem(value: 'standard', child: Text('Standard')),
              DropdownMenuItem(value: 'detailed', child: Text('Detailed')),
            ],
            onChanged: (v) => setState(() => length = v ?? 'standard'),
            decoration: const InputDecoration(labelText: 'Report length'),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed:
                busy ||
                    access!['eligible'] != true ||
                    access!['acceptingRequests'] != true ||
                    (access!['credits'] as num? ?? 0) < 1 ||
                    history.any(
                      (r) => [
                        'queued',
                        'researching',
                        'awaiting_review',
                      ].contains(r['status']),
                    )
                ? null
                : () {
                    if (question.text.trim().length < 20) {
                      notice(
                        context,
                        'Ask a specific question of at least 20 characters.',
                      );
                      return;
                    }
                    submit();
                  },
            child: const Text('Start investigation · 1 credit'),
          ),
        ],
        heading('Your notebook'),
        if (history.isEmpty) copy('Refresh to load your investigations.'),
        ...history.map(
          (r) => Card(
            child: Column(
              children: [
                ListTile(
                  title: Text(r['question'] ?? ''),
                  subtitle: Text(
                    '${r['status']} · ${r['stage'] ?? r['reportLength'] ?? ''}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) =>
                          Investigation(api: widget.api, id: r['id']),
                    ),
                  ),
                ),
                if (r['status'] == 'queued')
                  TextButton(
                    onPressed: busy
                        ? null
                        : () async {
                            try {
                              await widget.api.call(
                                '/sherlock/requests/${Uri.encodeComponent(r['id'])}/cancel',
                                method: 'POST',
                                authenticated: true,
                              );
                              await load();
                            } catch (e) {
                              if (context.mounted) notice(context, e);
                            }
                          },
                    child: const Text('Cancel & return credit'),
                  ),
              ],
            ),
          ),
        ),
      ],
      if (busy) const LinearProgressIndicator(),
      if (error != null) copy(error!),
    ],
  );
}

class Investigation extends StatefulWidget {
  const Investigation({super.key, required this.api, required this.id});
  final Api api;
  final String id;
  @override
  State<Investigation> createState() => _InvestigationState();
}

class _InvestigationState extends State<Investigation> {
  Json? item;
  String? error;
  bool downloading = false;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final result = await widget.api.call(
        '/sherlock/requests/${Uri.encodeComponent(widget.id)}',
        authenticated: true,
      );
      if (mounted) {
        setState(() {
          item = result;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> pdf() async {
    final owner = widget.api.user?.uid;
    setState(() => downloading = true);
    try {
      final response = await widget.api.response(
        '/sherlock/requests/${Uri.encodeComponent(widget.id)}/report.pdf',
        authenticated: true,
      );
      if (!(response.headers['content-type'] ?? '').contains(
        'application/pdf',
      )) {
        throw Exception('The PDF is not available yet.');
      }
      final dir = await getTemporaryDirectory();
      final file = File(
        '${dir.path}/weaware-sherlock-${DateTime.now().microsecondsSinceEpoch}.pdf',
      );
      if (widget.api.user?.uid != owner || !mounted) return;
      await file.writeAsBytes(response.bodyBytes);
      try {
        await SharePlus.instance.share(
          ShareParams(
            files: [XFile(file.path)],
            subject: 'WeAware research report',
          ),
        );
      } finally {
        if (await file.exists()) await file.delete();
      }
    } catch (e) {
      if (mounted) notice(context, e);
    } finally {
      if (mounted) setState(() => downloading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final report = item?['report'] as Map?;
    final claims = objects(report?['claims']);
    final sources = objects(report?['sources']);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Research notebook'),
        actions: [
          IconButton(
            onPressed: load,
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(22),
        children: [
          if (error != null) copy(error!),
          if (item == null && error == null) const LinearProgressIndicator(),
          if (item != null) ...[
            Text('${item!['status']} · ${item!['stage'] ?? ''}'),
            heading(report?['title'] ?? item!['question'] ?? 'Investigation'),
            if (report == null)
              copy(
                item!['status'] == 'awaiting_review'
                    ? 'The draft is with the editor. It will appear after approval.'
                    : ['queued', 'researching'].contains(item!['status'])
                    ? 'Research is in progress. Estimated delivery: ${item!['dueAt'] ?? 'Pending'}. Use Refresh to check progress.'
                    : item!['status'] == 'cancelled'
                    ? 'Investigation cancelled; your credit was returned.'
                    : 'This investigation could not be completed. Your credit has been returned.',
              ),
            if (report != null) ...[
              copy(report['answer'] ?? ''),
              copy(
                'Research cutoff: ${report['cutoff'] ?? ''} · Editor reviewed',
              ),
              FilledButton.icon(
                onPressed: downloading ? null : pdf,
                icon: const Icon(Icons.picture_as_pdf),
                label: Text(
                  downloading ? 'Preparing PDF…' : 'Save or share PDF',
                ),
              ),
              ...objects(report['sections']).map(
                (section) => Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    heading(section['heading'] ?? ''),
                    ...objects(section['paragraphs']).map(
                      (p) => Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          copy(p['text'] ?? ''),
                          if (strings(p['claimIds']).isNotEmpty)
                            ExpansionTile(
                              title: const Text('Inspect the evidence'),
                              children: claims
                                  .where(
                                    (c) => strings(
                                      p['claimIds'],
                                    ).contains(c['id']),
                                  )
                                  .map(
                                    (c) => Padding(
                                      padding: const EdgeInsets.all(12),
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          copy(
                                            '${c['finding']} · ${c['state'] ?? ''}',
                                          ),
                                          if (c['caveat'] != null)
                                            copy(c['caveat']),
                                          ...objects(c['evidence']).map((e) {
                                            final s = sources
                                                .where(
                                                  (s) =>
                                                      s['id'] == e['sourceId'],
                                                )
                                                .firstOrNull;
                                            return ListTile(
                                              title: Text(e['quote'] ?? ''),
                                              subtitle: Text(
                                                s?['title'] ??
                                                    e['sourceId'] ??
                                                    '',
                                              ),
                                              onTap: s?['url'] is String
                                                  ? () => openLink(s!['url'])
                                                  : null,
                                            );
                                          }),
                                        ],
                                      ),
                                    ),
                                  )
                                  .toList(),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              heading('What remains unknown'),
              ...strings(report['unknowns']).map(copy),
              heading('Research limitations'),
              ...strings(report['limitations']).map(copy),
              copy(
                '${report['retrievalGaps'] ?? 0} candidate sources unavailable or duplicated. Accessible web text only.',
              ),
              heading('Source notebook'),
              ...sources.map(
                (s) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(s['title'] ?? 'Source'),
                  subtitle: Text(
                    '${s['publisherHost'] ?? ''} · ${s['publishedAt'] ?? 'Date unavailable'}',
                  ),
                  trailing: const Icon(Icons.open_in_new),
                  onTap: s['url'] is String ? () => openLink(s['url']) : null,
                ),
              ),
              if (objects(report['searchDiscovery']).isNotEmpty)
                heading('Google Search discovery'),
              ...objects(report['searchDiscovery']).map(
                (search) => ExpansionTile(
                  title: Text(search['query'] ?? 'Discovery results'),
                  children: [
                    copy(search['text'] ?? ''),
                    ...objects(search['sources']).map(
                      (s) => ListTile(
                        title: Text(s['title'] ?? 'Source'),
                        onTap: s['url'] is String
                            ? () => openLink(s['url'])
                            : null,
                      ),
                    ),
                  ],
                ),
              ),
              copy(
                report['disclosure'] ??
                    'AI-assisted research with editorial review.',
              ),
            ],
          ],
        ],
      ),
    );
  }
}

class Editorial extends StatefulWidget {
  const Editorial({super.key, required this.api});
  final Api api;
  @override
  State<Editorial> createState() => _EditorialState();
}

class _EditorialState extends State<Editorial> {
  List<Json> drafts = [];
  String? error;
  bool busy = false;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() => busy = true);
    try {
      final r = await widget.api.call(
        '/editorial/podcasts/drafts',
        authenticated: true,
      );
      if (mounted) {
        setState(() {
          drafts = objects(r['drafts']);
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Editorial review'),
      actions: [
        IconButton(
          onPressed: busy ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(22),
      children: [
        copy(
          'Authorized editors can review scripts and sources before publication. Approval starts audio generation and publishes the episode when ready.',
        ),
        if (busy) const LinearProgressIndicator(),
        if (error != null) copy(error!),
        if (!busy && error == null && drafts.isEmpty)
          copy('No drafts awaiting review.'),
        ...drafts.map(
          (d) => Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  heading(d['title'] ?? 'Draft'),
                  copy(d['description'] ?? ''),
                  copy(d['script'] ?? ''),
                  ...objects(d['sources']).map(
                    (s) => ListTile(
                      title: Text(s['outlet'] ?? s['title'] ?? 'Source'),
                      onTap: s['url'] is String
                          ? () => openLink(s['url'])
                          : null,
                    ),
                  ),
                  FilledButton(
                    onPressed: busy
                        ? null
                        : () async {
                            final approve = await showDialog<bool>(
                              context: context,
                              builder: (c) => AlertDialog(
                                title: const Text('Approve this episode?'),
                                content: const Text(
                                  'This starts audio generation and publishes the episode when ready.',
                                ),
                                actions: [
                                  TextButton(
                                    onPressed: () => Navigator.pop(c, false),
                                    child: const Text('Keep reviewing'),
                                  ),
                                  FilledButton(
                                    onPressed: () => Navigator.pop(c, true),
                                    child: const Text('Approve & publish'),
                                  ),
                                ],
                              ),
                            );
                            if (approve != true) return;
                            setState(() => busy = true);
                            try {
                              await widget.api.call(
                                '/editorial/podcasts/drafts/${Uri.encodeComponent(d['id'])}/approve',
                                method: 'POST',
                                authenticated: true,
                              );
                              if (context.mounted) {
                                notice(
                                  context,
                                  'Approved. Audio is generating; refresh Listen shortly.',
                                );
                              }
                              await load();
                            } catch (e) {
                              if (context.mounted) notice(context, e);
                            } finally {
                              if (mounted) setState(() => busy = false);
                            }
                          },
                    child: const Text('Approve episode'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    ),
  );
}
