import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

import 'api.dart';

/// Complete excerpts only: no generated assertions or headline-as-summary fallback.
List<String> articleFacts(Json article) {
  final candidates = <String>[];
  final explicit = article['keyFacts'];
  if (explicit is List) candidates.addAll(explicit.whereType<String>());
  if (candidates.isEmpty) {
    final body = article['body'];
    if (body is List) {
      for (final paragraph in body.whereType<String>()) {
        candidates.addAll(_sentences(paragraph));
      }
    }
    if (candidates.isEmpty) {
      final summary = article['summary'];
      if (summary is String) candidates.addAll(_sentences(summary));
    }
  }
  final seen = <String>{};
  return candidates
      .map((value) => value.replaceAll(RegExp(r'\s+'), ' ').trim())
      .where((value) => value.isNotEmpty && value != article['title'])
      .where((value) => seen.add(value.toLowerCase()))
      .take(3)
      .toList();
}

List<String> _sentences(String value) {
  final text = value.replaceAll(RegExp(r'\s+'), ' ').trim();
  if (text.isEmpty) return [];
  final result = <String>[];
  var start = 0;
  for (var i = 0; i < text.length; i++) {
    if (!'.!?'.contains(text[i])) continue;
    if (text[i] == '.') {
      if (i > 0 &&
          i + 1 < text.length &&
          RegExp(r'\d').hasMatch(text[i - 1]) &&
          RegExp(r'\d').hasMatch(text[i + 1])) {
        continue;
      }
      final prefix = text.substring(start, i + 1);
      if (RegExp(
        r'(?:\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc)|\b[A-Z]|(?:\b[A-Za-z]\.){2,})\.$',
        caseSensitive: false,
      ).hasMatch(prefix)) {
        continue;
      }
    }
    var end = i + 1;
    while (end < text.length && '"”’\')'.contains(text[end])) {
      end++;
    }
    if (end < text.length && text[end] != ' ') continue;
    result.add(text.substring(start, end).trim());
    start = end;
    while (start < text.length && text[start] == ' ') {
      start++;
    }
    i = start - 1;
  }
  if (start < text.length) result.add(text.substring(start).trim());
  return result;
}

abstract class DiscoveryStore {
  Future<Json> read(String scope);
  Future<void> write(String scope, Json data);
}

class FileDiscoveryStore implements DiscoveryStore {
  Future<File> _file(String scope) async {
    final directory = await getApplicationSupportDirectory();
    final name = base64Url.encode(utf8.encode(scope)).replaceAll('=', '');
    return File('${directory.path}/discovery-$name.json');
  }

  @override
  Future<Json> read(String scope) async {
    final file = await _file(scope);
    if (!await file.exists()) return {};
    return Map<String, dynamic>.from(
      jsonDecode(await file.readAsString()) as Map,
    );
  }

  @override
  Future<void> write(String scope, Json data) async {
    final file = await _file(scope);
    await file.parent.create(recursive: true);
    final temporary = File('${file.path}.tmp');
    await temporary.writeAsString(jsonEncode(data), flush: true);
    await temporary.rename(file.path);
  }
}

class Discover extends StatefulWidget {
  const Discover({
    super.key,
    required this.api,
    required this.onOpen,
    required this.onSignIn,
    this.store,
  });
  final Api api;
  final ValueChanged<Json> onOpen;
  final VoidCallback onSignIn;
  final DiscoveryStore? store;
  @override
  State<Discover> createState() => _DiscoverState();
}

class _DiscoverState extends State<Discover> {
  late final DiscoveryStore store = widget.store ?? FileDiscoveryStore();
  late final String scope = widget.api.user?.uid ?? 'guest';
  List<Json> articles = [];
  final Map<String, Json> saved = {};
  final Set<String> skipped = {};
  bool busy = true;
  String? error, storageError;
  int offset = 0, total = 0;
  double drag = 0;
  Future<void> writes = Future.value();
  Json? lastArticle;
  bool lastWasSave = false;
  List<Json> get remaining => articles
      .where((a) => !skipped.contains(a['id']) && !saved.containsKey(a['id']))
      .toList();

  @override
  void initState() {
    super.initState();
    _restoreAndLoad();
  }

  Future<void> _restoreAndLoad() async {
    try {
      final data = await store.read(scope);
      if (!mounted) return;
      for (final article in _objects(data['saved'])) {
        if (article['id'] is String) saved[article['id']] = article;
      }
      skipped.addAll((data['skipped'] as List? ?? []).whereType<String>());
    } catch (_) {
      if (mounted) {
        setState(
          () => storageError =
              'Saved stories could not be loaded on this device.',
        );
      }
    }
    await load();
  }

  Future<void> persist() {
    final data = <String, dynamic>{
      'saved': saved.values.toList(),
      'skipped': skipped.toList(),
    };
    writes = writes
        .catchError((_) {})
        .then((_) async {
          await store.write(scope, data);
          if (mounted && storageError != null) {
            setState(() => storageError = null);
          }
        })
        .catchError((_) {
          if (mounted) {
            setState(
              () => storageError =
                  'Your choices could not be saved on this device. Please retry.',
            );
          }
        });
    return writes;
  }

  Future<void> load({bool more = false}) async {
    if (mounted) {
      setState(() {
        busy = true;
        error = null;
      });
    }
    try {
      final nextOffset = more ? offset : 0;
      final result = await widget.api.call(
        '/articles?limit=${widget.api.user == null ? 9 : 24}&offset=$nextOffset',
      );
      if (!mounted) return;
      final next = _objects(result['articles']);
      setState(() {
        articles = more ? [...articles, ...next] : next;
        if (widget.api.user == null) articles = articles.take(3).toList();
        offset = nextOffset + next.length;
        total = result['total'] as int? ?? offset;
      });
    } catch (_) {
      if (mounted) {
        setState(
          () => error = 'Stories could not be loaded. Please try again.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  void choose(Json article, bool save) {
    final id = article['id'];
    if (id is! String) return;
    setState(() {
      drag = 0;
      lastArticle = article;
      lastWasSave = save;
      if (save) {
        saved[id] = article;
        skipped.remove(id);
      } else {
        skipped.add(id);
        saved.remove(id);
      }
    });
    persist();
  }

  void undo() {
    final article = lastArticle;
    if (article == null) return;
    setState(() {
      saved.remove(article['id']);
      skipped.remove(article['id']);
      lastArticle = null;
    });
    persist();
  }

  @override
  Widget build(BuildContext context) {
    final deck = remaining;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 12, 8),
          child: Row(
            children: [
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'DISCOVER',
                      style: TextStyle(fontSize: 11, letterSpacing: 2),
                    ),
                    Text(
                      'The facts. Then your call.',
                      style: TextStyle(
                        fontFamily: 'serif',
                        fontSize: 23,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
              TextButton.icon(
                onPressed: () => showSaved(context),
                icon: const Icon(Icons.bookmark_outline),
                label: Text('Saved (${saved.length})'),
              ),
            ],
          ),
        ),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 20),
          child: Text(
            'Swipe left to skip. Swipe right to save. Choices stay on this device.',
            style: TextStyle(fontSize: 12),
          ),
        ),
        if (storageError != null)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Text(storageError!),
          ),
        if (busy) const LinearProgressIndicator(),
        if (error != null)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              children: [
                Text(error!),
                TextButton(onPressed: load, child: const Text('Retry')),
              ],
            ),
          ),
        Expanded(
          child: deck.isEmpty
              ? Center(
                  child: SingleChildScrollView(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.done_all,
                            size: 44,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                          const SizedBox(height: 12),
                          Text(
                            busy ? 'Loading stories…' : 'You’re all caught up.',
                            style: Theme.of(context).textTheme.headlineSmall,
                          ),
                          const SizedBox(height: 8),
                          const Text(
                            'Your saved stories are ready whenever you are.',
                            textAlign: TextAlign.center,
                          ),
                          if (!busy &&
                              widget.api.user != null &&
                              offset < total)
                            FilledButton(
                              onPressed: () => load(more: true),
                              child: const Text('More stories'),
                            ),
                          if (!busy && widget.api.user == null)
                            FilledButton(
                              onPressed: widget.onSignIn,
                              child: const Text('Sign in for more stories'),
                            ),
                          if (skipped.isNotEmpty)
                            TextButton(
                              onPressed: () {
                                setState(() {
                                  skipped.clear();
                                  lastArticle = null;
                                });
                                persist();
                              },
                              child: const Text('Revisit skipped stories'),
                            ),
                        ],
                      ),
                    ),
                  ),
                )
              : GestureDetector(
                  onHorizontalDragUpdate: (details) =>
                      setState(() => drag += details.delta.dx),
                  onHorizontalDragEnd: (_) {
                    if (drag.abs() >= 85) {
                      choose(deck.first, drag > 0);
                    } else {
                      setState(() => drag = 0);
                    }
                  },
                  onHorizontalDragCancel: () => setState(() => drag = 0),
                  child: Transform.translate(
                    offset: Offset(drag.clamp(-120, 120), 0),
                    child: Transform.rotate(
                      angle: drag / 2500,
                      child: Card(
                        margin: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                        clipBehavior: Clip.antiAlias,
                        child: Stack(
                          children: [
                            SingleChildScrollView(
                              child: Padding(
                                padding: const EdgeInsets.all(20),
                                child: FactCard(
                                  article: deck.first,
                                  onOpen: () => widget.onOpen(deck.first),
                                ),
                              ),
                            ),
                            if (drag.abs() > 25)
                              Positioned(
                                top: 12,
                                right: 12,
                                child: Chip(
                                  label: Text(drag > 0 ? 'SAVE' : 'SKIP'),
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
        ),
        if (lastArticle != null)
          TextButton.icon(
            onPressed: undo,
            icon: const Icon(Icons.undo, size: 17),
            label: Text('Undo ${lastWasSave ? 'save' : 'skip'}'),
          ),
        if (deck.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 4, 20, 12),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => choose(deck.first, false),
                    icon: const Icon(Icons.close),
                    label: const Text('Skip'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: () => choose(deck.first, true),
                    icon: const Icon(Icons.bookmark_add_outlined),
                    label: const Text('Save'),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Future<void> showSaved(BuildContext context) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => Scaffold(
          appBar: AppBar(title: const Text('Saved stories')),
          body: saved.isEmpty
              ? const Center(
                  child: Text('Swipe right on a story to save it here.'),
                )
              : ListView(
                  padding: const EdgeInsets.all(20),
                  children: saved.values
                      .map(
                        (article) => Card(
                          child: ListTile(
                            title: Text(
                              article['title']?.toString() ?? 'Story',
                            ),
                            subtitle: Text(
                              '${article['topic'] ?? 'News'} · ${_consensus(article)} source agreement',
                            ),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () => widget.onOpen(article),
                          ),
                        ),
                      )
                      .toList(),
                ),
        ),
      ),
    );
  }
}

List<Json> _objects(dynamic value) => (value is List ? value : [])
    .whereType<Map>()
    .map((item) => Map<String, dynamic>.from(item))
    .toList();
String _consensus(Json article) {
  final score = num.tryParse('${article['consensus']}');
  return score == null || !score.isFinite || score < 0 || score > 100
      ? 'Unscored'
      : '${score.toStringAsFixed(score == score.roundToDouble() ? 0 : 1)}%';
}

class FactCard extends StatelessWidget {
  const FactCard({super.key, required this.article, required this.onOpen});
  final Json article;
  final VoidCallback onOpen;
  @override
  Widget build(BuildContext context) {
    final facts = articleFacts(article);
    final sources = _objects(article['sources']);
    final warnings = _objects(article['flaggedClaims']);
    final published = DateTime.tryParse(
      article['publishedAt']?.toString() ?? '',
    );
    final date = published == null
        ? ''
        : MaterialLocalizations.of(
            context,
          ).formatMediumDate(published.toLocal());
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '${article['topic'] ?? 'News'}${date.isEmpty ? '' : ' · $date'}',
          style: TextStyle(
            color: Theme.of(context).colorScheme.primary,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 10),
        Text(
          article['title']?.toString() ?? 'Story',
          style: const TextStyle(
            fontFamily: 'serif',
            fontSize: 25,
            height: 1.2,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 8,
          runSpacing: 6,
          children: [
            Chip(
              avatar: const Icon(Icons.fact_check_outlined, size: 18),
              label: Text(
                _consensus(article) == 'Unscored'
                    ? 'Consensus unavailable'
                    : '${_consensus(article)} consensus',
              ),
            ),
            Chip(label: Text('${sources.length} sources')),
          ],
        ),
        const Text(
          'Source agreement, not a guarantee of accuracy.',
          style: TextStyle(fontSize: 11),
        ),
        const SizedBox(height: 18),
        const Text(
          'KEY FACTS',
          style: TextStyle(
            fontSize: 11,
            letterSpacing: 1.8,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 10),
        if (facts.isEmpty)
          const Text(
            'No factual brief is available. Open the reporting for details.',
          ),
        ...facts.map(
          (fact) => Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('•  ', style: TextStyle(fontSize: 17)),
                Expanded(
                  child: Text(
                    fact,
                    style: const TextStyle(fontSize: 16, height: 1.45),
                  ),
                ),
              ],
            ),
          ),
        ),
        if (warnings.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 6, bottom: 8),
            child: Text(
              '${warnings.length} ${warnings.length == 1 ? 'claim needs' : 'claims need'} closer inspection. See source notes.',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        if (sources.isNotEmpty)
          Text(
            'Reporting: ${sources.map((s) => s['outlet']).whereType<String>().toSet().join(' · ')}',
            style: const TextStyle(fontSize: 12),
          ),
        const SizedBox(height: 12),
        TextButton.icon(
          onPressed: onOpen,
          icon: const Icon(Icons.open_in_new, size: 18),
          label: const Text('Read story & sources'),
        ),
      ],
    );
  }
}
