import Foundation

struct Article: Codable, Identifiable {
    let id: String; let topic: String; let title: String; let summary: String
    let body: [String]; let image: String?; let sources: [Source]; let flaggedClaims: [Flag]
    let consensus: Double; let readMins: Int; let publishedAt: String?
}
struct Source: Codable { let outlet: String; let url: String?; let stance: String?; let note: String? }
struct Flag: Codable { let claim: String; let reason: String }
struct Feed: Decodable { let articles: [Article]; let total: Int }
struct Topics: Decodable { let topics: [String] }
struct Episode: Decodable, Identifiable {
    let id: String; let title: String; let description: String; let topic: String
    let audioUrl: String; let durationSeconds: Double; let sourceUrls: [String]
}
struct Episodes: Decodable { let episodes: [Episode] }
struct AudioStatus: Decodable { let status: String; let audioUrl: String?; let error: String? }
struct Preferences: Decodable { let subscribed: Bool; let topics: [String]; let cadence: String; let deliveryReady: Bool? }
struct Entitlement: Decodable { let eligible: Bool; let credits: Int; let acceptingRequests: Bool }
struct InvestigationList: Decodable { let requests: [Investigation] }
struct Investigation: Decodable, Identifiable {
    let id: String; let question: String; let status: String; let stage: String?; let errorCode: String?; let reportLength: String?; let report: Report?
}
struct Report: Decodable {
    let title: String; let answer: String; let cutoff: String; let disclosure: String
    let searchDiscovery: [SearchDiscovery]?
    let sections: [ReportSection]; let claims: [Claim]; let sources: [ReportSource]; let unknowns: [String]; let limitations: [String]
}
struct ReportSection: Decodable { let heading: String; let paragraphs: [Paragraph] }
struct Paragraph: Decodable { let text: String; let claimIds: [String] }
struct Claim: Decodable { let id: String; let finding: String; let state: String; let caveat: String?; let evidence: [Evidence] }
struct Evidence: Decodable { let sourceId: String; let quote: String }
struct ReportSource: Decodable { let id: String; let title: String; let url: String; let publisherHost: String? }
struct Draft: Decodable, Identifiable { let id: String; let title: String; let script: String; let sourceUrls: [String] }
struct Drafts: Decodable { let drafts: [Draft] }

struct SearchDiscovery: Decodable { let query: String; let text: String; let sources: [DiscoverySource] }
struct DiscoverySource: Decodable { let title: String?; let url: String }

extension Article {
    /// Verbatim sentences only: no generated claims, compressed numbers, or removed qualifiers.
    var keyPoints: [String] {
        var points: [String] = []
        let paragraphs = body.filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
        let text = (paragraphs.isEmpty ? [summary] : paragraphs).joined(separator: "\n")
        text.enumerateSubstrings(in: text.startIndex..<text.endIndex, options: [.bySentences, .localized]) { sentence, _, _, stop in
            guard let sentence else { return }
            let clean = sentence.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !clean.isEmpty, !points.contains(clean), clean != title else { return }
            points.append(clean)
            if points.count == 3 { stop = true }
        }
        return points
    }
}

/// Public story snapshots and decisions stay on this device, separately for each account.
struct DiscoverHistory: Codable {
    var saved: [Article] = []
    var skipped: [String] = []
    var savedIDs: Set<String> { Set(saved.map(\.id)) }
    var seenIDs: Set<String> { savedIDs.union(skipped) }

    mutating func save(_ article: Article) {
        saved.removeAll { $0.id == article.id }
        saved.insert(article, at: 0)
        skipped.removeAll { $0 == article.id }
    }
    mutating func skip(_ id: String) {
        if !skipped.contains(id) { skipped.append(id) }
    }
    mutating func removeSaved(_ id: String) { saved.removeAll { $0.id == id } }
    static func storageKey(scope: String) -> String { "weaware.discover.v1.\(scope)" }
    static func load(scope: String, defaults: UserDefaults = .standard) -> Self {
        guard let data = defaults.data(forKey: storageKey(scope: scope)), let result = try? JSONDecoder().decode(Self.self, from: data) else { return Self() }
        return result
    }
    func persist(scope: String, defaults: UserDefaults = .standard) throws {
        defaults.set(try JSONEncoder().encode(self), forKey: Self.storageKey(scope: scope))
    }
}
