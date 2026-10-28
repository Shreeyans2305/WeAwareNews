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
    }.padding(20) }.navigationTitle("Today's edition").navigationBarTitleDisplayMode(.inline).searchable(text: $query, prompt: "Search reporting").task(id: "\(topic)|\(query)|\(account.signedIn)") { try? await Task.sleep(for: .milliseconds(300)); guard !Task.isCancelled else { return }; await load() }.refreshable { await load() }.sheet(isPresented: $showAuth) { NavigationStack { AccountView() } } }
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
