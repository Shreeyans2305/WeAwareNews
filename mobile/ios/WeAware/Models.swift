import Foundation

struct Article: Decodable, Identifiable {
    let id: String; let topic: String; let title: String; let summary: String
    let body: [String]; let image: String?; let sources: [Source]; let flaggedClaims: [Flag]
    let consensus: Double; let readMins: Int; let publishedAt: String?
}
struct Source: Decodable { let outlet: String; let url: String?; let stance: String?; let note: String? }
struct Flag: Decodable { let claim: String; let reason: String }
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
