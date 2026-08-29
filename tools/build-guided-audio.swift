// Turns a timed script into one guided-meditation file.
//
//   xcrun swift tools/build-guided-audio.swift <script.json> <segments-dir> <out.m4a> <seconds>
//
// The segments arrive as separate speech clips; what makes the result a
// meditation rather than a recitation is the silence between them. Each clip
// is placed at the second the script asks for, on a timeline as long as the
// sitting, so the voice starts you off, returns a few times, and closes —
// and the rest is quiet, which is the practice.
//
// Silence is not synthesised: an empty range in an AVMutableComposition track
// is already silence, and exporting the composition writes it out.

import Foundation
import AVFoundation

let args = CommandLine.arguments
guard args.count > 4 else {
    fatalError("build-guided-audio.swift <script.json> <segments-dir> <out.m4a> <seconds>")
}
let scriptURL = URL(fileURLWithPath: args[1])
let segDir = URL(fileURLWithPath: args[2])
let outURL = URL(fileURLWithPath: args[3])
let hossz = Double(args[4])!

struct Szegmens: Codable { let at: Double; let szoveg: String }
struct Terv: Codable { let id: String; let cim: String; let hossz: Int; let szegmensek: [Szegmens] }

let terv = try JSONDecoder().decode(Terv.self, from: Data(contentsOf: scriptURL))

let komp = AVMutableComposition()
guard let sav = komp.addMutableTrack(withMediaType: .audio,
                                     preferredTrackID: kCMPersistentTrackID_Invalid) else {
    fatalError("nem sikerult savot letrehozni")
}

let sema = CMTimeScale(600)
var utolsoVege = CMTime.zero
var atfedes = 0

for (i, sz) in terv.szegmensek.enumerated() {
    let f = segDir.appendingPathComponent(String(format: "%02d.mp3", i))
    guard FileManager.default.fileExists(atPath: f.path) else {
        fatalError("hianyzo szegmens: \(f.lastPathComponent)")
    }
    let eszkoz = AVURLAsset(url: f)
    let sav2 = eszkoz.tracks(withMediaType: .audio)
    guard let forras = sav2.first else { fatalError("nincs hangsav: \(f.lastPathComponent)") }
    let idotartam = eszkoz.duration

    var kezdet = CMTime(seconds: sz.at, preferredTimescale: sema)
    // A clip that would start before the previous one finished is pushed back
    // rather than overlapped — two voices at once is not a meditation. The
    // review catches this in the script, but the audio must not depend on it.
    if kezdet < utolsoVege {
        atfedes += 1
        kezdet = utolsoVege
    }
    try sav.insertTimeRange(CMTimeRange(start: .zero, duration: idotartam),
                            of: forras, at: kezdet)
    utolsoVege = kezdet + idotartam
}

// Pad to the full sitting: the tail silence is what lets the practice settle
// before the timer ends.
let cel = CMTime(seconds: hossz, preferredTimescale: sema)
if utolsoVege < cel {
    sav.insertEmptyTimeRange(CMTimeRange(start: utolsoVege, end: cel))
}

try? FileManager.default.removeItem(at: outURL)
guard let export = AVAssetExportSession(asset: komp, presetName: AVAssetExportPresetAppleM4A) else {
    fatalError("nem sikerult exportot letrehozni")
}
export.outputURL = outURL
export.outputFileType = .m4a

let varakozas = DispatchSemaphore(value: 0)
export.exportAsynchronously { varakozas.signal() }
varakozas.wait()

guard export.status == .completed else {
    fatalError("export hiba: \(export.error?.localizedDescription ?? "ismeretlen")")
}

let kesz = AVURLAsset(url: outURL)
let meret = (try? FileManager.default.attributesOfItem(atPath: outURL.path)[.size] as? Int) ?? 0
let beszed = terv.szegmensek.count
print(String(format: "  %@ — %d szegmens, %.0f mp hang, %.1f MB",
             terv.cim, beszed, CMTimeGetSeconds(kesz.duration), Double(meret ?? 0)/1024/1024))
if atfedes > 0 { print("  FIGYELEM: \(atfedes) szegmenst hatrebb kellett tolni (atfedes)") }
