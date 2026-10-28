import SwiftUI
struct PodcastsView: View {
    @EnvironmentObject var audio: AudioPlayer; @EnvironmentObject var account: Account
    @State private var episodes: [Episode] = []; @State private var articles: [Article] = []; @State private var drafts: [Draft] = []; @State private var message = ""; @State private var loading = true; @State private var reviewing = false
    var body: some View { List {
        Section { NewsHeading(eyebrow: "The listening desk", title: "Hear every side.", subtitle: "Published briefings, AI narration and the sources behind each story.") }
        if loading { ProgressView() }; if !message.isEmpty { Notice(text: message) }
        Section("Published episodes") {
            if episodes.isEmpty && !loading { Text("Reviewed episodes will appear here after publication.").foregroundStyle(.secondary) }
            ForEach(episodes) { episode in VStack(alignment: .leading, spacing: 10) { Text(episode.topic.uppercased()).font(.caption); Text(episode.title).font(.system(.title3, design: .serif, weight: .semibold)); Text(episode.description).font(.subheadline).foregroundStyle(.secondary); Button { audio.episodes(episodes, selected: episode.id) } label: { Label("Play · \(max(1, Int(ceil(episode.durationSeconds / 60)))) min · AI narration", systemImage: "play.circle.fill") }; DisclosureGroup("Source notes") { ForEach(episode.sourceUrls, id: \.self) { value in if let url = URL(string: value), ["http", "https"].contains(url.scheme ?? "") { Link(url.host ?? value, destination: url).font(.footnote) } } } }.padding(.vertical, 8) }
        }
        Section("Top five on the go") { Button { audio.articles(Array(articles.prefix(5))) } label: { Label("Play top five stories", systemImage: "text.line.first.and.arrowtriangle.forward") }.disabled(articles.isEmpty)
            ForEach(articles.prefix(5)) { article in Button { audio.articles(Array(articles.drop(while: { $0.id != article.id }))) } label: { Label(article.title, systemImage: "play.circle") }.font(.subheadline) }
        }
        Section("Follow the shows") { ShareLink(item: URL(string: AppConfig.origin + "/podcasts/feed.xml")!) { Label("Share podcast RSS feed", systemImage: "square.and.arrow.up") } }
        if account.signedIn && account.verified { Section("Editorial review") { Button("Load podcast drafts") { Task { await loadDrafts() } }.disabled(reviewing)
            ForEach(drafts) { draft in DisclosureGroup(draft.title) { Text(draft.script).font(.system(.body, design: .serif)).textSelection(.enabled); ForEach(draft.sourceUrls, id: \.self) { value in if let url = URL(string: value) { Link(url.host ?? value, destination: url) } }; Button("Approve reviewed script and generate audio") { Task { await approve(draft) } }.disabled(reviewing) } }
            Text("Only accounts on the server’s editor allowlist can review drafts.").font(.caption).foregroundStyle(.secondary)
        } }
    }.navigationTitle("Listen").task { await load() }.refreshable { await load() } }
    func load() async { loading = true; message = ""; do { let result: Episodes = try await API.get("/api/v1/podcasts/episodes"); episodes = result.episodes; let feed: Feed = try await API.get("/api/v1/articles?limit=5"); articles = feed.articles } catch { message = error.localizedDescription }; loading = false }
    func loadDrafts() async { reviewing = true; do { let result: Drafts = try await API.get("/api/v1/editorial/podcasts/drafts", token: account.token()); drafts = result.drafts; message = drafts.isEmpty ? "No scripts awaiting review." : "" } catch { message = error.localizedDescription }; reviewing = false }
    func approve(_ draft: Draft) async { reviewing = true; do { _ = try await API.data("/api/v1/editorial/podcasts/drafts/\(API.id(draft.id))/approve", method: "POST", token: account.token()); drafts.removeAll { $0.id == draft.id }; message = "Script approved. Audio generation is queued." } catch { message = error.localizedDescription }; reviewing = false }
}
