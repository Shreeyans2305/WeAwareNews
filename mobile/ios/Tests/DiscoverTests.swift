import Foundation

@main struct DiscoverChecks {
    static func main() throws {
        let article = Article(id: "test-id", topic: "Science", title: "A headline is not a fact packet", summary: "Officials said 12 people may be affected. The cause remains under investigation.", body: ["Officials said 12 people may be affected. The cause remains under investigation.", "No evacuation order has been issued. A fourth sentence is outside the card."], image: nil, sources: [], flaggedClaims: [], consensus: 75, readMins: 2, publishedAt: nil)
        precondition(article.keyPoints == ["Officials said 12 people may be affected.", "The cause remains under investigation.", "No evacuation order has been issued."])
        let empty = Article(id: "empty", topic: "Other", title: "Headline must never become an invented bullet", summary: "", body: [], image: nil, sources: [], flaggedClaims: [], consensus: 0, readMins: 1, publishedAt: nil)
        precondition(empty.keyPoints.isEmpty)
        let suite = "news.weaware.discover.tests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        var choices = DiscoverHistory()
        choices.skip(article.id)
        precondition(choices.seenIDs.contains(article.id))
        choices.save(article)
        precondition(!choices.skipped.contains(article.id))
        try choices.persist(scope: "account-a", defaults: defaults)
        precondition(DiscoverHistory.load(scope: "account-a", defaults: defaults).saved.first?.keyPoints == article.keyPoints)
        precondition(DiscoverHistory.load(scope: "guest", defaults: defaults).saved.isEmpty)
        precondition(DiscoverHistory.load(scope: "account-b", defaults: defaults).saved.isEmpty)
        choices.removeSaved(article.id)
        precondition(choices.savedIDs.isEmpty)
        print("Discover fact selection, persistence and account isolation checks passed")
    }
}
