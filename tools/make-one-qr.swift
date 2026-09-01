// The single install code.
//
//   swift tools/make-one-qr.swift [out.png]
//
// One QR pointing at a collection file on the reader's own Drive; the app
// walks its listed manifests and installs everything in one pass — the public
// catalog and the private Drive bundles alike. The private ids live in the
// collection file on Drive, never in the public repo.
//
// Needs the app's collection support (build 21+): older builds reject the
// collection JSON as "manifest", installing nothing — which is the safe
// failure, not a partial install.
import Foundation
import CoreImage
import CoreImage.CIFilterBuiltins
import CoreText
import ImageIO
import UniformTypeIdentifiers

let LINK = "https://drive.google.com/file/d/1hE-beuvJuC0ecVudm0eh2YXT14PIaehH/view"

let ctx = CIContext()
func qr(_ s: String, _ oldal: CGFloat) -> CGImage {
    let f = CIFilter.qrCodeGenerator()
    f.message = Data(s.utf8); f.correctionLevel = "M"
    let k = f.outputImage!
    let sk = oldal / k.extent.width
    return ctx.createCGImage(k.transformed(by: .init(scaleX: sk, y: sk)),
                             from: k.extent.applying(.init(scaleX: sk, y: sk)))!
}

let W: CGFloat = 1500, H: CGFloat = 1150
let c = CGContext(data: nil, width: Int(W), height: Int(H), bitsPerComponent: 8, bytesPerRow: 0,
                  space: CGColorSpace(name: CGColorSpace.sRGB)!,
                  bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
c.setFillColor(CGColor(srgbRed: 1, green: 1, blue: 1, alpha: 1))
c.fill(CGRect(x: 0, y: 0, width: W, height: H))

func ir(_ s: String, _ meret: CGFloat, _ y: CGFloat, _ szurke: CGFloat, felkover: Bool = false) {
    let attrs: [CFString: Any] = [
        kCTFontAttributeName: CTFontCreateWithName((felkover ? "HelveticaNeue-Bold" : "HelveticaNeue-Medium") as CFString, meret, nil),
        kCTForegroundColorAttributeName: CGColor(srgbRed: szurke, green: szurke, blue: szurke, alpha: 1)]
    let line = CTLineCreateWithAttributedString(
        NSAttributedString(string: s, attributes: attrs as? [NSAttributedString.Key: Any] ?? [:]))
    let w = CTLineGetTypographicBounds(line, nil, nil, nil)
    c.textPosition = CGPoint(x: (W - CGFloat(w)) / 2, y: y)
    CTLineDraw(line, c)
}

ir("Az Önuralom Tükre", 58, H - 110, 0.08, felkover: true)
ir("AZ EGYETLEN KÓD — minden egyben", 36, H - 170, 0.35)

let oldal: CGFloat = 640
c.interpolationQuality = .none
c.draw(qr(LINK, oldal), in: CGRect(x: (W - oldal) / 2, y: H - 210 - oldal, width: oldal, height: oldal))
c.interpolationQuality = .default

ir("Modulok → + → QR beolvasása", 34, H - 210 - oldal - 70, 0.15)
ir("75 modul · 736 gyakorlat · hangoskönyv 76 sáv · 203 Bashar-felvétel · vezetett meditációk", 26, H - 210 - oldal - 125, 0.45)
ir("Build 21-től működik", 24, H - 210 - oldal - 180, 0.55)

let out = CommandLine.arguments.count > 1
    ? URL(fileURLWithPath: CommandLine.arguments[1])
    : FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Desktop/AZ EGYETLEN KOD.png")
let dest = CGImageDestinationCreateWithURL(out as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, c.makeImage()!, nil)
CGImageDestinationFinalize(dest)

let be = CIImage(contentsOf: out)!
let det = CIDetector(ofType: CIDetectorTypeQRCode, context: ctx,
                     options: [CIDetectorAccuracy: CIDetectorAccuracyHigh])!
let talalt = Set(det.features(in: be).compactMap { ($0 as? CIQRCodeFeature)?.messageString })
print(talalt.contains(LINK)
      ? "OK: \(out.path) — a kód visszaolvasva"
      : "HIBA: a kód nem olvasható vissza")
