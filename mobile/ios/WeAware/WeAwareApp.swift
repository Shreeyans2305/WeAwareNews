import SwiftUI

@main struct WeAwareApp: App {
    @StateObject private var account = Account(); @StateObject private var audio = AudioPlayer()
    @AppStorage("appearance") private var appearance = "system"
    var body: some Scene { WindowGroup { RootView().environmentObject(account).environmentObject(audio).tint(.primary).preferredColorScheme(appearance == "system" ? nil : appearance == "dark" ? .dark : .light) } }
}
struct RootView: View {
    var body: some View { TabView {
        NavigationStack { FeedView() }.tabItem { Label("News", systemImage: "newspaper") }
        NavigationStack { PodcastsView() }.tabItem { Label("Listen", systemImage: "headphones") }
        NavigationStack { NewsletterView() }.tabItem { Label("Crosscheck", systemImage: "envelope") }
        NavigationStack { SherlockView() }.tabItem { Label("Sherlock", systemImage: "magnifyingglass") }
        NavigationStack { AccountView() }.tabItem { Label("Account", systemImage: "person.crop.circle") }
    }.safeAreaInset(edge: .bottom, spacing: 0) { PlayerBar() } }
}
struct Notice: View { let text: String; var body: some View { Text(text).font(.callout).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading).padding().background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 12)) } }
struct NewsHeading: View { let eyebrow: String; let title: String; let subtitle: String
    var body: some View { VStack(alignment: .leading, spacing: 12) { Text(eyebrow.uppercased()).font(.caption.weight(.semibold)).tracking(3); Text(title).font(.system(.largeTitle, design: .serif, weight: .bold)); Text(subtitle).font(.system(.body, design: .serif)).foregroundStyle(.secondary); Rectangle().frame(height: 3) }.padding(.vertical, 12) }
}
struct FeedView: View {
    @EnvironmentObject var account: Account
    @State private var showDiscover = false
    @State private var articles: [Article] = []; @State private var topics = ["All"]; @State private var topic = "All"; @State private var query = ""; @State private var error = ""; @State private var loading = true; @State private var total = 0; @State private var showAuth = false; @State private var generation = UUID()
    var body: some View { ScrollView { LazyVStack(alignment: .leading, spacing: 22) {
        NewsHeading(eyebrow: "The independent reading room", title: "WeAware", subtitle: "Many sources. A clearer picture.")
        ScrollView(.horizontal, showsIndicators: false) { HStack { ForEach(topics, id: \.self) { item in Button { topic = item } label: { Text(item).font(.subheadline.weight(.semibold)).padding(.horizontal, 15).padding(.vertical, 9).background(topic == item ? Color.primary.opacity(0.15) : Color.secondary.opacity(0.06), in: Capsule()) } } } }
        if loading && articles.isEmpty { ProgressView().frame(maxWidth: .infinity) }
        if !error.isEmpty { Notice(text: error); Button("Try again") { Task { await load() } } }
        if !loading && articles.isEmpty && error.isEmpty { Notice(text: "No stories match this search. Try another topic or phrase.") }
        ForEach(Array(articles.enumerated()), id: \.element.id) { index, article in
            if account.signedIn || index < 3 { NavigationLink { ReaderView(article: article) } label: { StoryCard(article: article) }.buttonStyle(.plain) }
            else { Button { showAuth = true } label: { StoryCard(article: article).overlay(alignment: .topTrailing) { Image(systemName: "lock.fill").padding(10).background(.regularMaterial, in: Circle()) } }.buttonStyle(.plain) }
            Divider()
        }
        if account.signedIn && articles.count < total { Button("Load more stories") { Task { await load(more: true) } }.disabled(loading).frame(maxWidth: .infinity) }
        if !account.signedIn { Notice(text: "Guests can preview nine stories and read the first three. Sign in for the complete feed."); Button("Sign in to keep reading") { showAuth = true } }
    }.padding(20) }.navigationTitle("Today's edition").navigationBarTitleDisplayMode(.inline)
    .toolbar { ToolbarItem(placement: .topBarTrailing) { Button { showDiscover = true } label: { Label("Discover", systemImage: "rectangle.on.rectangle.angled") }.accessibilityIdentifier("news.discover") } }
    .sheet(isPresented: $showDiscover) { NavigationStack { DiscoverView() } }.searchable(text: $query, prompt: "Search reporting").task(id: "\(topic)|\(query)|\(account.signedIn)") { try? await Task.sleep(for: .milliseconds(300)); guard !Task.isCancelled else { return }; await load() }.refreshable { await load() }.sheet(isPresented: $showAuth) { NavigationStack { AccountView() } } }
    func load(more: Bool = false) async {
        let requestID = UUID(); generation = requestID; loading = true; error = ""
        do {
            let offset = more ? articles.count : 0
            var components = URLComponents(); components.queryItems = [URLQueryItem(name: "limit", value: account.signedIn ? "24" : "9"), URLQueryItem(name: "offset", value: "\(offset)"), URLQueryItem(name: "topic", value: topic), URLQueryItem(name: "q", value: query)]
            let feed: Feed = try await API.get("/api/v1/articles?\(components.percentEncodedQuery ?? "")")
            guard generation == requestID, !Task.isCancelled else { return }
            articles = more ? articles + feed.articles : feed.articles; total = feed.total
            if topics.count == 1 { let result: Topics = try await API.get("/api/v1/topics"); topics = ["All"] + result.topics }
        } catch is CancellationError {} catch { if generation == requestID { self.error = error.localizedDescription } }
        if generation == requestID { loading = false }
    }
}
struct StoryCard: View {
    let article: Article
    var body: some View { VStack(alignment: .leading, spacing: 12) {
        if let image = article.image, let url = URL(string: image) { AsyncImage(url: url) { image in image.resizable().scaledToFill() } placeholder: { Rectangle().fill(Color.secondary.opacity(0.1)).overlay(Image(systemName: "newspaper").font(.largeTitle)) }.frame(height: 190).clipped().clipShape(RoundedRectangle(cornerRadius: 10)) }
        Text("\(article.topic.uppercased())  ·  \(article.readMins) MIN READ").font(.caption.weight(.semibold)).tracking(1)
        Text(article.title).font(.system(.title2, design: .serif, weight: .semibold)).fixedSize(horizontal: false, vertical: true)
        Text(article.summary).font(.subheadline).foregroundStyle(.secondary).lineLimit(3)
        Label("\(article.sources.count) sources · \(Int(article.consensus))% agreement", systemImage: "checkmark.seal").font(.caption).foregroundStyle(.secondary)
    }.contentShape(Rectangle()) }
}
struct ReaderView: View {
    @State var article: Article; @EnvironmentObject var audio: AudioPlayer
    @State private var error = ""
    @AppStorage("likedArticles") private var likedArticles = ""
    var liked: Bool { likedArticles.components(separatedBy: "|").contains(article.id) }
    var body: some View { ScrollView { VStack(alignment: .leading, spacing: 22) {
        StoryCard(article: article)
        HStack { Button { audio.narrate(article) } label: { Label("Listen", systemImage: "play.circle.fill") }; Spacer(); Button { var values = Set(likedArticles.components(separatedBy: "|").filter { !$0.isEmpty }); if liked { values.remove(article.id) } else { values.insert(article.id) }; likedArticles = values.sorted().joined(separator: "|") } label: { Image(systemName: liked ? "heart.fill" : "heart").accessibilityLabel(liked ? "Unlike story" : "Like story") }; ShareLink(item: URL(string: "https://weaware.news/s/\(API.id(article.id))")!) { Label("Share", systemImage: "square.and.arrow.up") } }
        Text("AI-assisted reporting and narration. Open the linked sources to inspect important claims.").font(.caption).foregroundStyle(.secondary)
        ForEach(Array(article.body.enumerated()), id: \.offset) { _, paragraph in Text(paragraph).font(.system(.body, design: .serif)).lineSpacing(6).textSelection(.enabled) }
        Divider(); Text("The source notebook").font(.system(.title2, design: .serif, weight: .bold))
        Text("\(Int(article.consensus))% source agreement").font(.headline); ProgressView(value: min(100, max(0, article.consensus)), total: 100)
        Notice(text: "Agreement is an automated signal, not a measure of truth.")
        ForEach(Array(article.sources.enumerated()), id: \.offset) { _, source in VStack(alignment: .leading, spacing: 6) {
            if let value = source.url, let url = URL(string: value), ["https", "http"].contains(url.scheme ?? "") { Link(source.outlet, destination: url).font(.headline) } else { Text(source.outlet).font(.headline) }
            Text(source.stance == "agree" ? "Corroborates" : source.stance == "context" ? "Adds context" : "Disputes").font(.caption).foregroundStyle(.secondary)
            if let note = source.note { Text(note).font(.subheadline) }
        }.padding(.vertical, 6) }
        Text("Claims to inspect").font(.headline)
        if article.flaggedClaims.isEmpty { Notice(text: "No low-confidence claims were flagged. Automated checks can miss errors.") }
        ForEach(Array(article.flaggedClaims.enumerated()), id: \.offset) { _, flag in VStack(alignment: .leading, spacing: 8) { Label(flag.claim, systemImage: "exclamationmark.triangle").font(.headline); Text(flag.reason) }.padding().background(Color.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 12)) }
        if !error.isEmpty { Notice(text: error) }
    }.padding(20) }.navigationTitle(article.topic).navigationBarTitleDisplayMode(.inline).task { do { article = try await API.get("/api/v1/articles/\(API.id(article.id))") } catch { self.error = error.localizedDescription } } }
}

struct DiscoverView: View {
    @EnvironmentObject private var account: Account
    @Environment(\.dismiss) private var dismiss
    @State private var articles: [Article] = []
    @State private var history = DiscoverHistory()
    @State private var previous: DiscoverHistory?
    @State private var loading = false
    @State private var error = ""
    @State private var status = ""
    @State private var offset = 0
    @State private var total = 0
    @State private var loadID = UUID()
    @State private var drag = CGSize.zero
    @State private var deciding = false
    @State private var showSaved = false
    @State private var showAuth = false
    @State private var sourceArticle: Article?
    private var scope: String { account.user?.id ?? "guest" }
    private var current: Article? { articles.first { !history.seenIDs.contains($0.id) } }
    private var canLoadMore: Bool { account.signedIn && offset < total }
    private func readable(_ article: Article) -> Bool { account.signedIn || articles.prefix(3).contains { $0.id == article.id } }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("More than a headline.").font(.system(.title, design: .serif, weight: .bold))
                Text("The key points, source agreement and evidence. Swipe right to save, left to skip.").font(.subheadline).foregroundStyle(.secondary)
                if loading && articles.isEmpty { ProgressView("Loading reporting…").frame(maxWidth: .infinity) }
                if !error.isEmpty { Notice(text: error); Button("Try again") { Task { await load(reset: articles.isEmpty) } } }
                if let article = current {
                    DiscoverCard(article: article, direction: drag.width, sources: { sourceArticle = article })
                        .offset(x: drag.width, y: 0)
                        .rotationEffect(.degrees(Double(drag.width / 24)))
                        .simultaneousGesture(DragGesture(minimumDistance: 24)
                            .onChanged { value in if abs(value.translation.width) > abs(value.translation.height) { drag = value.translation } }
                            .onEnded { value in
                                if abs(value.translation.width) > 100 && abs(value.translation.width) > abs(value.translation.height) { decide(save: value.translation.width > 0) }
                                else { withAnimation(.spring()) { drag = .zero } }
                            })
                        .accessibilityAction(named: "Save story") { decide(save: true) }
                        .accessibilityAction(named: "Skip story") { decide(save: false) }
                    if readable(article) { NavigationLink { ReaderView(article: article) } label: { Label("Read the full reporting", systemImage: "doc.text") } }
                    else { Button("Sign in to read the full reporting") { showAuth = true } }
                } else if !loading && error.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("You're caught up", systemImage: "checkmark.circle").font(.title2.bold())
                        Text("Your saved stories are ready to revisit. Skipped stories stay out of your deck on this device.").foregroundStyle(.secondary)
                        if canLoadMore { Button("Load more stories") { Task { await load() } } }
                        if !account.signedIn { Button("Sign in for more reporting") { showAuth = true } }
                        if !history.skipped.isEmpty { Button("Revisit skipped stories") { previous = history; history.skipped = []; persist(); status = "Skipped stories returned to your deck." } }
                    }.padding(.vertical, 30)
                }
                if loading && !articles.isEmpty { ProgressView().frame(maxWidth: .infinity) }
                if !status.isEmpty { Text(status).font(.footnote).foregroundStyle(.secondary).accessibilityIdentifier("discover.status") }
                Text("Saved and skipped stories stay on this device, separately for each account. Key points are verbatim sentences from the published reporting; no extra claims are generated.").font(.caption).foregroundStyle(.secondary)
            }.padding(20)
        }
        .navigationTitle("Discover").navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarLeading) { Button("Done") { dismiss() } }
            ToolbarItem(placement: .topBarTrailing) { Button { showSaved = true } label: { Label("Saved (\(history.saved.count))", systemImage: "bookmark") }.accessibilityIdentifier("discover.saved") }
        }
        .safeAreaInset(edge: .bottom) {
            HStack(spacing: 20) {
                Button { decide(save: false) } label: { Label("Skip", systemImage: "xmark").frame(maxWidth: .infinity) }.buttonStyle(.bordered).disabled(current == nil)
                Button { if let previous { history = previous; self.previous = nil; persist(); status = "Last swipe undone." } } label: { Image(systemName: "arrow.uturn.backward").accessibilityLabel("Undo last swipe") }.disabled(previous == nil)
                Button { decide(save: true) } label: { Label("Save", systemImage: "bookmark.fill").frame(maxWidth: .infinity) }.buttonStyle(.borderedProminent).disabled(current == nil)
            }.disabled(deciding).padding().background(.regularMaterial)
        }
        .task(id: scope) { history = DiscoverHistory.load(scope: scope); previous = nil; status = ""; await load(reset: true) }
        .sheet(isPresented: $showSaved) { NavigationStack { savedStories } }
        .sheet(isPresented: $showAuth) { NavigationStack { AccountView() } }
        .sheet(item: $sourceArticle) { article in NavigationStack { DiscoverSources(article: article) } }
    }

    private var savedStories: some View {
        List {
            Section { Text("Saved on this device for \(account.signedIn ? "your account" : "guest reading").").font(.footnote).foregroundStyle(.secondary) }
            if history.saved.isEmpty { Text("Swipe right or tap Save on a story to keep it here.").foregroundStyle(.secondary) }
            ForEach(history.saved) { article in
                VStack(alignment: .leading, spacing: 8) {
                    if readable(article) { NavigationLink { ReaderView(article: article) } label: { savedLabel(article) } }
                    else { Button { showSaved = false; showAuth = true } label: { savedLabel(article) }.buttonStyle(.plain) }
                    Button("Remove saved story", role: .destructive) { history.removeSaved(article.id); persist() }.font(.caption)
                }.padding(.vertical, 5)
            }
        }.navigationTitle("Saved stories").toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { showSaved = false } } }
    }
    private func savedLabel(_ article: Article) -> some View {
        VStack(alignment: .leading, spacing: 5) { Text(article.title).font(.system(.headline, design: .serif)); Text("\(article.topic) · \(Int(article.consensus))% source agreement · \(article.sources.count) sources").font(.caption).foregroundStyle(.secondary) }
    }
    private func persist() {
        do { try history.persist(scope: scope) }
        catch { self.error = "Your story choices could not be saved. Please try again." }
    }
    private func decide(save: Bool) {
        guard let article = current, !deciding else { return }
        deciding = true
        let owner = scope
        let original = history
        withAnimation(.easeOut(duration: 0.15)) { drag = CGSize(width: save ? 460 : -460, height: 0) }
        Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(160))
            guard scope == owner else { deciding = false; drag = .zero; return }
            previous = original
            if save { history.save(article) } else { history.skip(article.id) }
            persist(); status = save ? "Saved for later." : "Skipped. You can undo this swipe."
            drag = .zero; deciding = false
            if current == nil && canLoadMore { await load() }
        }
    }
    private func load(reset: Bool = false) async {
        guard !loading || reset else { return }
        let requestID = UUID(); loadID = requestID
        let owner = scope
        loading = true; error = ""
        if reset { articles = []; offset = 0; total = 0 }
        defer { if loadID == requestID { loading = false } }
        do {
            let feed: Feed = try await API.get("/api/v1/articles?limit=\(account.signedIn ? 24 : 9)&offset=\(offset)")
            guard scope == owner, loadID == requestID, !Task.isCancelled else { return }
            let known = Set(articles.map(\.id))
            articles.append(contentsOf: feed.articles.filter { !known.contains($0.id) })
            offset += feed.articles.count; total = feed.total
            if feed.articles.isEmpty { total = offset }
        } catch is CancellationError { }
        catch { if scope == owner && loadID == requestID { self.error = error.localizedDescription } }
    }
}

private struct DiscoverCard: View {
    let article: Article
    let direction: CGFloat
    let sources: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            if let image = article.image, let url = URL(string: image) {
                AsyncImage(url: url) { image in image.resizable().scaledToFill() } placeholder: { Rectangle().fill(Color.secondary.opacity(0.1)) }
                    .frame(height: 130).clipped().clipShape(RoundedRectangle(cornerRadius: 12))
            }
            HStack { Text(article.topic.uppercased()).tracking(1); Spacer(); Text("\(article.sources.count) SOURCES") }.font(.caption.weight(.semibold))
            Text(article.title).font(.system(.title2, design: .serif, weight: .bold)).fixedSize(horizontal: false, vertical: true)
            HStack(alignment: .firstTextBaseline) { Text("\(Int(min(100, max(0, article.consensus))))%").font(.title2.bold()); Text("source agreement").font(.subheadline); Spacer(); Text("\(article.readMins) min read").font(.caption).foregroundStyle(.secondary) }
            ProgressView(value: min(100, max(0, article.consensus)), total: 100).tint(.primary)
            Text("KEY POINTS").font(.caption.weight(.bold)).tracking(1)
            if article.keyPoints.isEmpty { Text("A published summary is not available. Open the reporting and sources for details.").font(.subheadline).foregroundStyle(.secondary) }
            ForEach(Array(article.keyPoints.enumerated()), id: \.offset) { _, point in HStack(alignment: .top, spacing: 9) { Text("•").fontWeight(.bold); Text(point).font(.subheadline).fixedSize(horizontal: false, vertical: true) } }
            if !article.flaggedClaims.isEmpty { Label("\(article.flaggedClaims.count) flagged claim\(article.flaggedClaims.count == 1 ? "" : "s") to inspect", systemImage: "exclamationmark.triangle").font(.caption).foregroundStyle(.orange) }
            Button(action: sources) { Label("Evidence and source notes", systemImage: "books.vertical") }.font(.subheadline.weight(.semibold))
            Text("Agreement is an automated signal, not a truth score.").font(.caption2).foregroundStyle(.secondary)
        }
        .padding(20).background(Color(uiColor: .secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 20))
        .overlay(alignment: .topTrailing) { if abs(direction) > 25 { Text(direction > 0 ? "SAVE" : "SKIP").font(.title2.bold()).padding(10).background(.regularMaterial, in: RoundedRectangle(cornerRadius: 10)).padding() } }
        .overlay { RoundedRectangle(cornerRadius: 20).stroke(Color.primary.opacity(0.1)) }
        .accessibilityElement(children: .contain)
    }
}

private struct DiscoverSources: View {
    let article: Article
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        List {
            Section { Text(article.title).font(.system(.headline, design: .serif)); Text("\(Int(article.consensus))% source agreement · \(article.sources.count) sources"); Text("Agreement is an automated signal, not a truth score.").font(.caption).foregroundStyle(.secondary) }
            Section("Source notebook") {
                ForEach(Array(article.sources.enumerated()), id: \.offset) { _, source in
                    VStack(alignment: .leading, spacing: 6) {
                        if let raw = source.url, let url = URL(string: raw), ["http", "https"].contains(url.scheme ?? "") { Link(source.outlet, destination: url).font(.headline) }
                        else { Text(source.outlet).font(.headline) }
                        Text(source.stance == "agree" ? "Corroborates" : source.stance == "context" ? "Adds context" : source.stance == "dispute" ? "Disputes" : "Source").font(.caption).foregroundStyle(.secondary)
                        if let note = source.note, !note.isEmpty { Text(note).font(.subheadline) }
                    }
                }
            }
            if !article.flaggedClaims.isEmpty { Section("Claims to inspect") { ForEach(Array(article.flaggedClaims.enumerated()), id: \.offset) { _, flag in VStack(alignment: .leading, spacing: 6) { Text(flag.claim).font(.headline); Text(flag.reason).font(.subheadline) } } } }
        }.navigationTitle("Evidence").toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } } }
    }
}
