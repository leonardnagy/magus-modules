// One sheet with every install QR on it.
//
//   swift tools/make-all-qr.swift [out.png]
//
// Three sources, three codes: the public catalog, and two that point into the
// reader's own Drive. They cannot be merged — a private Drive id has no place
// in a public manifest — so the sheet names each one instead.
import Foundation
import CoreImage
import CoreImage.CIFilterBuiltins
import CoreText
import ImageIO
import UniformTypeIdentifiers

struct Kod { let cim: String; let alcim: String; let hol: String; let link: String }

let kodok = [
  Kod(cim: "Katalógus",
      alcim: "75 modul · 736 gyakorlat · 83 idézet",
      hol: "Modulok → + → Minden telepítése",
      link: "https://raw.githubusercontent.com/leonardnagy/magus-modules/main/everything.json"),
  Kod(cim: "A csodák tanítása",
      alcim: "hangoskönyv · 76 sáv · 3 kötet",
      hol: "Meditációk → QR ikon",
      link: "https://drive.google.com/file/d/1ZovnG6oEhjQBb3RGbEnv_Gz-7OVusyuj/view"),
  Kod(cim: "Bashar — meditációk",
      alcim: "203 felvétel · 3 csoport",
      hol: "Meditációk → QR ikon",
      link: "https://drive.google.com/file/d/1tuTxe7sYA_MYHxsf7_pzCo9NGPeXH1Ri/view"),
]

let ctx = CIContext()
func qr(_ s: String, _ oldal: CGFloat) -> CGImage {
    let f = CIFilter.qrCodeGenerator()
    f.message = Data(s.utf8); f.correctionLevel = "M"
    let k = f.outputImage!
    let sk = oldal / k.extent.width
    return ctx.createCGImage(k.transformed(by: .init(scaleX: sk, y: sk)),
                             from: k.extent.applying(.init(scaleX: sk, y: sk)))!
}

let W: CGFloat = 1500, H: CGFloat = 700 * CGFloat(kodok.count) + 200
let c = CGContext(data: nil, width: Int(W), height: Int(H), bitsPerComponent: 8, bytesPerRow: 0,
                  space: CGColorSpace(name: CGColorSpace.sRGB)!,
                  bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
c.setFillColor(CGColor(srgbRed: 1, green: 1, blue: 1, alpha: 1))
c.fill(CGRect(x: 0, y: 0, width: W, height: H))

func ir(_ s: String, _ meret: CGFloat, _ x: CGFloat, _ y: CGFloat, _ szurke: CGFloat, kozepre: Bool = false) {
    let attrs: [CFString: Any] = [
        kCTFontAttributeName: CTFontCreateWithName("HelveticaNeue-Medium" as CFString, meret, nil),
        kCTForegroundColorAttributeName: CGColor(srgbRed: szurke, green: szurke, blue: szurke, alpha: 1)]
    let line = CTLineCreateWithAttributedString(
        NSAttributedString(string: s, attributes: attrs as? [NSAttributedString.Key: Any] ?? [:]))
    let w = CTLineGetTypographicBounds(line, nil, nil, nil)
    c.textPosition = CGPoint(x: kozepre ? (W - CGFloat(w))/2 : x, y: y)
    CTLineDraw(line, c)
}

ir("Az Önuralom Tükre — telepítés", 54, 0, H - 100, 0.08, kozepre: true)

let oldal: CGFloat = 480
for (i, k) in kodok.enumerated() {
    let teto = H - 180 - CGFloat(i) * 700
    c.interpolationQuality = .none
    c.draw(qr(k.link, oldal), in: CGRect(x: 90, y: teto - oldal, width: oldal, height: oldal))
    c.interpolationQuality = .default
    let sx: CGFloat = 90 + oldal + 70
    ir("\(i + 1).", 40, sx, teto - 70, 0.65)
    ir(k.cim, 46, sx + 70, teto - 70, 0.08)
    ir(k.alcim, 29, sx + 70, teto - 120, 0.45)
    ir(k.hol, 29, sx + 70, teto - 185, 0.30)
}

let out = CommandLine.arguments.count > 1
    ? URL(fileURLWithPath: CommandLine.arguments[1])
    : FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Desktop/Telepites QR.png")
let dest = CGImageDestinationCreateWithURL(out as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, c.makeImage()!, nil)
CGImageDestinationFinalize(dest)

// Read every code back: a sheet whose codes do not scan is worse than none.
let be = CIImage(contentsOf: out)!
let det = CIDetector(ofType: CIDetectorTypeQRCode, context: ctx,
                     options: [CIDetectorAccuracy: CIDetectorAccuracyHigh])!
let talalt = Set(det.features(in: be).compactMap { ($0 as? CIQRCodeFeature)?.messageString })
let hianyzik = kodok.map(\.link).filter { !talalt.contains($0) }
print(hianyzik.isEmpty
      ? "OK: \(out.path) — mind a \(kodok.count) kód visszaolvasva"
      : "HIBA: nem olvasható vissza: \(hianyzik)")
