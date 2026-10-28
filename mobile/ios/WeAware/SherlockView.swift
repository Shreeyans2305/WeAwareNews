import SwiftUI
struct SherlockView: View {
    @EnvironmentObject var account: Account
    @State private var access: Entitlement?; @State private var requests: [Investigation] = []
    @State private var question = ""; @State private var scope = ""; @State private var length = "standard"; @State private var consent = false
    @State private var submissionKey = UUID().uuidString; @State private var message = ""; @State private var busy = false
    var active: Bool { requests.contains { ["queued", "researching", "awaiting_review"].contains($0.status) } }
    var body: some View { Form {
        Section { NewsHeading(eyebrow: "Journalist Jeff / Research", title: "A question worth looking into.", subtitle: "Ask about a claim, event or topic. Receive an editor-reviewed brief with the evidence open for inspection."); Notice(text: "This invitation-only pilot checks accessible public sources. Breaking news and obscure topics may have limited evidence.") }
        if !account.signedIn || !account.verified { Notice(text: "Sign in and verify your email in Account to use Sherlock Mode.") }
        else {
            Section("Research access") { Text("\(access?.credits ?? 0) research credits available"); if access?.eligible != true { Text("Your account needs an invitation to this pilot.").foregroundStyle(.secondary) }; if access?.acceptingRequests != true { Text("New investigations are currently unavailable.").foregroundStyle(.secondary) } }
            Section("Your question") { TextField("A specific research question", text: $question, axis: .vertical).lineLimit(3...8).onChange(of: question) { _, _ in submissionKey = UUID().uuidString }; Text("\(question.count)/1,200 characters · minimum 20").font(.caption).foregroundStyle(.secondary); TextField("Scope or context (optional)", text: $scope, axis: .vertical).lineLimit(2...5).onChange(of: scope) { _, _ in submissionKey = UUID().uuidString }; Picker("Report length", selection: $length) { Text("Brief · 400–700 words").tag("brief"); Text("Standard · 800–1,500 words").tag("standard"); Text("Detailed · 1,500–2,400 words").tag("detailed") }.onChange(of: length) { _, _ in submissionKey = UUID().uuidString }; Toggle("I understand this is AI-assisted research that can contain errors and needs editorial review.", isOn: $consent)
                Button("Start investigation · 1 credit") { Task { await submit() } }.disabled(busy || !consent || question.trimmingCharacters(in: .whitespacesAndNewlines).count < 20 || question.count > 1200 || scope.count > 600 || access?.eligible != true || access?.acceptingRequests != true || (access?.credits ?? 0) < 1 || active)
            }
            Section("Research notebook") {
                if requests.isEmpty { Text("Your completed briefs will appear here.").foregroundStyle(.secondary) }
                ForEach(requests) { item in VStack(alignment: .leading, spacing: 8) { NavigationLink { InvestigationView(id: item.id) } label: { VStack(alignment: .leading, spacing: 6) { Text(item.question).font(.system(.headline, design: .serif)); Text(statusLabel(item.status)).font(.caption).foregroundStyle(.secondary); if let stage = item.stage { Text(stage.capitalized).font(.caption2) } } }; if item.status == "queued" { Button("Cancel and return credit", role: .destructive) { Task { await cancel(item.id) } }.disabled(busy) } } }
                Button("Refresh notebook") { Task { await refresh() } }.disabled(busy)
            }
        }
        if busy { ProgressView() }; if !message.isEmpty { Notice(text: message) }
    }.navigationTitle("Sherlock").task(id: "\(account.generation)|\(account.verified)") {
        access = nil; requests = []; question = ""; scope = ""; consent = false; message = ""
        guard account.signedIn && account.verified else { access = nil; requests = []; return }
        await refresh()
        while !Task.isCancelled { do { try await Task.sleep(for: .seconds(30)) } catch { return }; if active { await refresh() } }
    }.refreshable { await refresh() } }
    func refresh() async { guard account.signedIn && account.verified else { return }; let owner = account.generation; busy = true; do { let token = try await account.token(); let nextAccess: Entitlement = try await API.get("/api/v1/sherlock/entitlement", token: token); let list: InvestigationList = try await API.get("/api/v1/sherlock/requests", token: token); guard account.generation == owner else { busy = false; return }; access = nextAccess; requests = list.requests; message = "" } catch { message = error.localizedDescription }; busy = false }
    func submit() async { busy = true; do { _ = try await API.data("/api/v1/sherlock/requests", method: "POST", body: ["question": question.trimmingCharacters(in: .whitespacesAndNewlines), "scope": scope.trimmingCharacters(in: .whitespacesAndNewlines), "reportLength": length, "submissionKey": submissionKey], token: account.token()); question = ""; scope = ""; consent = false; submissionKey = UUID().uuidString; await refresh() } catch { message = error.localizedDescription }; busy = false }
    func cancel(_ id: String) async { busy = true; do { _ = try await API.data("/api/v1/sherlock/requests/\(API.id(id))/cancel", method: "POST", token: account.token()); await refresh() } catch { message = error.localizedDescription }; busy = false }
}
func statusLabel(_ value: String) -> String { ["queued": "On Jeff’s desk", "researching": "Following the evidence", "awaiting_review": "With the editor", "completed": "Ready to read", "failed": "Unable to complete", "cancelled": "Cancelled", "insufficient_evidence": "Evidence too limited"][value] ?? value.capitalized }
struct InvestigationView: View {
    let id: String; @EnvironmentObject var account: Account
    @State private var item: Investigation?; @State private var message = ""; @State private var pdf: URL?; @State private var downloading = false
    var body: some View { ScrollView { VStack(alignment: .leading, spacing: 20) {
        if let item {
            Text(item.question).font(.system(.title, design: .serif, weight: .bold)); Text(statusLabel(item.status)).font(.headline)
            if let report = item.report, item.status == "completed" {
                Text(report.title).font(.system(.largeTitle, design: .serif, weight: .bold)); Text(report.answer).font(.title3); Text("Editor reviewed · Research cutoff: \(report.cutoff)").font(.caption).foregroundStyle(.secondary)
                if let pdf { ShareLink(item: pdf) { Label("Share report PDF", systemImage: "square.and.arrow.up") } } else { Button { Task { await download() } } label: { Label(downloading ? "Preparing PDF…" : "Download report PDF", systemImage: "arrow.down.doc") }.disabled(downloading) }
                ForEach(Array(report.sections.enumerated()), id: \.offset) { _, section in Text(section.heading).font(.system(.title2, design: .serif, weight: .semibold)); ForEach(Array(section.paragraphs.enumerated()), id: \.offset) { _, paragraph in Text(paragraph.text).font(.system(.body, design: .serif)).lineSpacing(5).textSelection(.enabled); DisclosureGroup("Inspect the evidence · \(paragraph.claimIds.count) findings") { ForEach(paragraph.claimIds, id: \.self) { claimID in if let claim = report.claims.first(where: { $0.id == claimID }) { VStack(alignment: .leading, spacing: 8) { Text(claim.finding).bold(); Text(claim.state).font(.caption); if let caveat = claim.caveat { Text(caveat) }; ForEach(Array(claim.evidence.enumerated()), id: \.offset) { _, evidence in Text("“\(evidence.quote)”").italic(); if let source = report.sources.first(where: { $0.id == evidence.sourceId }), let url = URL(string: source.url) { Link(source.title, destination: url) } } }.padding(.vertical, 8) } } }.font(.subheadline) } }
                Text("What remains unknown").font(.headline); ForEach(report.unknowns, id: \.self) { Text("• " + $0) }
                Text("Research limitations").font(.headline); ForEach(report.limitations, id: \.self) { Text("• " + $0) }
                Text("The source notebook").font(.headline); ForEach(report.sources, id: \.id) { source in if let url = URL(string: source.url) { Link(source.title, destination: url); Text(source.publisherHost ?? "").font(.caption).foregroundStyle(.secondary) } }; if let discovery = report.searchDiscovery { Text("Google Search discovery").font(.headline); ForEach(Array(discovery.enumerated()), id: \.offset) { _, search in DisclosureGroup(search.query) { Text(search.text).font(.subheadline); ForEach(Array(search.sources.enumerated()), id: \.offset) { _, source in if let url = URL(string: source.url) { Link(source.title ?? "Source", destination: url) } } } } }; Notice(text: report.disclosure)
            } else { if let code = item.errorCode { Notice(text: "Research could not complete: " + code.replacingOccurrences(of: "_", with: " ")) }; Notice(text: "Reports become available after editorial approval. Pull to refresh for the latest status.") }
        } else if message.isEmpty { ProgressView() }
        if !message.isEmpty { Notice(text: message) }
    }.padding(20) }.navigationTitle("Research brief").navigationBarTitleDisplayMode(.inline).task {
        await load(); while !Task.isCancelled && ["queued", "researching", "awaiting_review"].contains(item?.status ?? "") { do { try await Task.sleep(for: .seconds(30)) } catch { return }; await load() }
    }.refreshable { await load() }.onDisappear { if let pdf { try? FileManager.default.removeItem(at: pdf) }; pdf = nil }.onChange(of: account.generation) { _, _ in item = nil; if let pdf { try? FileManager.default.removeItem(at: pdf) }; pdf = nil } }
    func load() async { let expected = account.generation; do { let result: Investigation = try await API.get("/api/v1/sherlock/requests/\(API.id(id))", token: account.token()); guard account.signedIn && account.generation == expected else { return }; item = result; message = "" } catch { message = error.localizedDescription } }
    func download() async { let expected = account.generation; downloading = true; do { let data = try await API.data("/api/v1/sherlock/requests/\(API.id(id))/report.pdf", token: account.token()); guard account.signedIn && account.generation == expected else { downloading = false; return }; guard data.starts(with: Data("%PDF".utf8)) else { throw APIError(message: "The report PDF is not ready.") }; let url = FileManager.default.temporaryDirectory.appendingPathComponent("weaware-report-\(UUID().uuidString).pdf"); try data.write(to: url, options: .completeFileProtection); pdf = url } catch { message = error.localizedDescription }; downloading = false }
}
