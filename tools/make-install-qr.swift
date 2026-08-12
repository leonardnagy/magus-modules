// The install card: one QR that carries everything.json.
//
//   swift tools/make-install-qr.swift [out.png]
//
// Kept in the repo because the scratch copies keep getting cleaned away and
// rewritten from memory, which is how a card ends up quoting stale counts.
import Foundation
import CoreImage
import CoreText
import CoreImage.CIFilterBuiltins
import ImageIO
import UniformTypeIdentifiers

let LINK = "https://raw.githubusercontent.com/leonardnagy/magus-modules/main/everything.json"
let FELIRAT = "Minden telepítése"
let ALCIM = "75 modul · 736 gyakorlat · 83 idézet"

let out = CommandLine.arguments.count > 1
    ? URL(fileURLWithPath: CommandLine.arguments[1])
    : FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Desktop/Minden telepitese QR.png")

let ctx = CIContext()
let qrF = CIFilter.qrCodeGenerator()
qrF.message = Data(LINK.utf8)
qrF.correctionLevel = "M"
let qrSide: CGFloat = 900
let qr = qrF.outputImage!
let skala = qrSide / qr.extent.width
let qrKep = ctx.createCGImage(qr.transformed(by: .init(scaleX: skala, y: skala)),
                              from: qr.extent.applying(.init(scaleX: skala, y: skala)))!

let W: CGFloat = 1100, H: CGFloat = 1300
let c = CGContext(data: nil, width: Int(W), height: Int(H), bitsPerComponent: 8, bytesPerRow: 0,
                  space: CGColorSpace(name: CGColorSpace.sRGB)!,
                  bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
c.setFillColor(CGColor(srgbRed: 1, green: 1, blue: 1, alpha: 1))
c.fill(CGRect(x: 0, y: 0, width: W, height: H))
c.interpolationQuality = .none          // a QR maradjon éles
c.draw(qrKep, in: CGRect(x: (W - qrSide)/2, y: 250, width: qrSide, height: qrSide))

func ir(_ s: String, _ meret: CGFloat, _ y: CGFloat, _ szurke: CGFloat) {
    // CoreText keys, not AppKit's: this runs without AppKit so the script
    // works the same from a terminal as it would inside an app.
    let attrs: [CFString: Any] = [
        kCTFontAttributeName: CTFontCreateWithName("HelveticaNeue-Medium" as CFString, meret, nil),
        kCTForegroundColorAttributeName: CGColor(srgbRed: szurke, green: szurke, blue: szurke, alpha: 1)]
    let line = CTLineCreateWithAttributedString(NSAttributedString(string: s, attributes: attrs as? [NSAttributedString.Key: Any] ?? [:]))
    let w = CTLineGetTypographicBounds(line, nil, nil, nil)
    c.textPosition = CGPoint(x: (W - CGFloat(w))/2, y: y)
    CTLineDraw(line, c)
}
ir(FELIRAT, 62, 1160, 0.08)
ir(ALCIM, 34, 1085, 0.45)
ir("Modulok → + → Minden telepítése", 30, 150, 0.5)

let dest = CGImageDestinationCreateWithURL(out as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, c.makeImage()!, nil)
CGImageDestinationFinalize(dest)

// Read it back: a card that does not scan is worse than no card.
let be = CIImage(contentsOf: out)!
let det = CIDetector(ofType: CIDetectorTypeQRCode, context: ctx,
                     options: [CIDetectorAccuracy: CIDetectorAccuracyHigh])!
let talalt = (det.features(in: be).first as? CIQRCodeFeature)?.messageString
print(talalt == LINK ? "OK: \(out.path)" : "HIBA: a QR nem olvasható vissza (\(talalt ?? "nil"))")
