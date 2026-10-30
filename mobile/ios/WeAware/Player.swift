import SwiftUI
import AVFoundation
import MediaPlayer

@MainActor final class AudioPlayer: ObservableObject {
    @Published var title = ""; @Published var playing = false; @Published var busy = false; @Published var error = ""
    @Published var position = 0.0; @Published var duration = 0.0; @Published var speed: Float = 1 { didSet { if playing { player?.rate = speed } } }
    private var generation = UUID(); private var statusObserver: NSKeyValueObservation?
    private var player: AVPlayer?; private var observer: Any?; private var task: Task<Void, Never>?
    private enum Item { case article(Article); case episode(Episode) }
    private var queue: [Item] = [] { didSet { canNext = !queue.isEmpty } }
    private var history: [Item] = [] { didSet { canPrevious = !history.isEmpty } }
    private var currentItem: Item?
    @Published var canNext = false; @Published var canPrevious = false
    private var endObserver: NSObjectProtocol?
    init() {
        MPRemoteCommandCenter.shared().playCommand.addTarget { [weak self] _ in Task { @MainActor in self?.play() }; return .success }
        MPRemoteCommandCenter.shared().pauseCommand.addTarget { [weak self] _ in Task { @MainActor in self?.pause() }; return .success }
        MPRemoteCommandCenter.shared().nextTrackCommand.addTarget { [weak self] _ in Task { @MainActor in self?.next() }; return .success }
        MPRemoteCommandCenter.shared().previousTrackCommand.addTarget { [weak self] _ in Task { @MainActor in self?.previous() }; return .success }
        MPRemoteCommandCenter.shared().skipForwardCommand.preferredIntervals = [15]
        MPRemoteCommandCenter.shared().skipForwardCommand.addTarget { [weak self] _ in Task { @MainActor in self?.skip(15) }; return .success }
    }
    func articles(_ articles: [Article]) { currentItem = nil; history = []; queue = articles.map(Item.article); next() }
    func episodes(_ episodes: [Episode], selected: String) {
        guard let index = episodes.firstIndex(where: { $0.id == selected }) else { return }
        history = Array(episodes.prefix(index)).map(Item.episode); currentItem = nil
        queue = Array(episodes.dropFirst(index)).map(Item.episode); next()
    }
    func next() { guard !queue.isEmpty else { return }; if let currentItem { history.append(currentItem) }; let item = queue.removeFirst(); begin(item) }
    func previous() { guard let item = history.popLast() else { return }; if let currentItem { queue.insert(currentItem, at: 0) }; begin(item) }
    private func begin(_ item: Item) {
        currentItem = item
        switch item { case .article(let article): narrate(article, fromQueue: true)
        case .episode(let episode): start(episode.audioUrl, title: episode.title, preserveQueue: true) }
    }
    func narrate(_ article: Article, fromQueue: Bool = false) {
        if !fromQueue { queue = []; history = []; currentItem = .article(article) }
        task?.cancel(); pause(); generation = UUID(); let current = generation; busy = true; title = article.title; error = ""
        task = Task {
            do {
                var audio: AudioStatus = try await API.get("/api/v1/articles/\(API.id(article.id))/audio", method: "POST")
                for _ in 0..<150 {
                    try Task.checkCancellation()
                    if audio.status == "ready", let url = audio.audioUrl { guard generation == current else { return }; busy = false; start(url, title: article.title, fromNarration: true); return }
                    if audio.status == "failed" { throw APIError(message: audio.error ?? "Narration could not be generated.") }
                    try await Task.sleep(for: .seconds(2)); audio = try await API.get("/api/v1/articles/\(API.id(article.id))/audio")
                }
                throw APIError(message: "Narration is still being prepared. Try again shortly.")
            } catch is CancellationError {} catch { if generation == current { self.error = error.localizedDescription } }; if generation == current { busy = false }
        }
    }
    func start(_ url: String, title: String, fromNarration: Bool = false, preserveQueue: Bool = false) {
        if !fromNarration { task?.cancel(); generation = UUID(); busy = false; if !preserveQueue { queue = []; history = []; currentItem = nil } }; error = ""
        guard let url = URL(string: url), ["https", "http"].contains(url.scheme ?? "") else { error = "Audio address is invalid."; return }
        pause(); if let observer { player?.removeTimeObserver(observer) }; if let endObserver { NotificationCenter.default.removeObserver(endObserver) }
        do { try AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio); try AVAudioSession.sharedInstance().setActive(true) } catch { self.error = error.localizedDescription; return }
        self.title = title; position = 0; duration = 0; player = AVPlayer(url: url)
        statusObserver = player?.currentItem?.observe(\.status, options: [.new]) { [weak self] item, _ in
            guard item.status == .failed else { return }; Task { @MainActor in self?.error = "Audio could not play. Retry the episode or narration to refresh its audio link."; self?.playing = false }
        }
        observer = player?.addPeriodicTimeObserver(forInterval: CMTime(seconds: 0.5, preferredTimescale: 600), queue: .main) { [weak self] time in
            Task { @MainActor in guard let self else { return }; self.position = time.seconds.isFinite ? time.seconds : 0; let value = self.player?.currentItem?.duration.seconds ?? 0; self.duration = value.isFinite ? value : 0; self.updateNowPlaying() }
        }
        endObserver = NotificationCenter.default.addObserver(forName: .AVPlayerItemDidPlayToEndTime, object: player?.currentItem, queue: .main) { [weak self] _ in Task { @MainActor in self?.playing = false; self?.next() } }
        play()
    }
    func play() { player?.playImmediately(atRate: speed); playing = player != nil; updateNowPlaying() }
    func pause() { player?.pause(); playing = false; updateNowPlaying() }
    func skip(_ seconds: Double) { player?.seek(to: CMTime(seconds: max(0, min(duration, position + seconds)), preferredTimescale: 600)) }
    func seek(_ seconds: Double) { player?.seek(to: CMTime(seconds: seconds, preferredTimescale: 600)) }
    func stop() { task?.cancel(); generation = UUID(); pause(); title = ""; queue = []; history = []; currentItem = nil; busy = false }
    func updateNowPlaying() { MPNowPlayingInfoCenter.default().nowPlayingInfo = [MPMediaItemPropertyTitle: title, MPMediaItemPropertyArtist: "WeAware · AI narration", MPMediaItemPropertyPlaybackDuration: duration, MPNowPlayingInfoPropertyElapsedPlaybackTime: position, MPNowPlayingInfoPropertyPlaybackRate: playing ? speed : 0] }
}
struct PlayerBar: View {
    @EnvironmentObject var audio: AudioPlayer
    var body: some View {
        if !audio.title.isEmpty {
            VStack(spacing: 8) {
                HStack(spacing: 10) {
                    Image(systemName: "waveform")
                    VStack(alignment: .leading) {
                        Text(audio.title).font(.caption.bold()).lineLimit(1)
                        Text(audio.busy ? "Preparing AI narration…" : "AI narration")
                            .font(.caption2).foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 4)
                    if audio.busy {
                        ProgressView().frame(width: 44, height: 44)
                    } else {
                        Button { audio.stop() } label: {
                            Image(systemName: "xmark")
                                .frame(width: 44, height: 44)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .background(Circle().fill(.primary.opacity(0.1)))
                        .accessibilityLabel("Close player")
                    }
                }

                if audio.busy {
                    ProgressView().frame(maxWidth: .infinity)
                } else {
                    HStack(spacing: 0) {
                        Button { audio.previous() } label: {
                            Image(systemName: "backward.end.fill")
                                .frame(width: 44, height: 48)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .background(Circle().fill(.primary.opacity(0.08)))
                        .disabled(!audio.canPrevious)
                        .opacity(audio.canPrevious ? 1 : 0.45)
                        .accessibilityLabel("Previous story")

                        Button { audio.skip(-15) } label: {
                            Image(systemName: "gobackward.15")
                                .font(.system(size: 21))
                                .frame(width: 48, height: 48)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .background(Circle().fill(.primary.opacity(0.08)))
                        .accessibilityLabel("Back 15 seconds")

                        Button { audio.playing ? audio.pause() : audio.play() } label: {
                            Image(systemName: audio.playing ? "pause.fill" : "play.fill")
                                .font(.system(size: 23, weight: .semibold))
                                .frame(width: 56, height: 56)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .background(Circle().fill(.primary.opacity(0.14)))
                        .accessibilityLabel(audio.playing ? "Pause" : "Play")

                        Button { audio.skip(15) } label: {
                            Image(systemName: "goforward.15")
                                .font(.system(size: 21))
                                .frame(width: 48, height: 48)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .background(Circle().fill(.primary.opacity(0.08)))
                        .accessibilityLabel("Forward 15 seconds")

                        Button { audio.next() } label: {
                            Image(systemName: "forward.end.fill")
                                .frame(width: 44, height: 48)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .background(Circle().fill(.primary.opacity(0.08)))
                        .disabled(!audio.canNext)
                        .opacity(audio.canNext ? 1 : 0.45)
                        .accessibilityLabel("Next story")
                    }
                    .frame(maxWidth: .infinity)

                    Picker("Playback speed", selection: $audio.speed) {
                            Text("0.75×").tag(Float(0.75))
                            Text("1×").tag(Float(1))
                            Text("1.25×").tag(Float(1.25))
                            Text("1.5×").tag(Float(1.5))
                            Text("2×").tag(Float(2))
                    }
                    .pickerStyle(.segmented)
                    .labelsHidden()
                    .frame(maxWidth: .infinity)
                }

                if audio.duration > 0 {
                    Slider(value: Binding(get: { audio.position }, set: { audio.seek($0) }), in: 0...max(1, audio.duration))
                        .accessibilityLabel("Playback position")
                }
                if !audio.error.isEmpty {
                    Text(audio.error).font(.caption).foregroundStyle(.red)
                }
            }
            .buttonStyle(.plain)
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(.regularMaterial)
        }
    }
}
