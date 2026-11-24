import Foundation
import Vision

struct Label: Encodable {
    let content: String
    let confidence: Float
    let bbox: [Double]
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
let supported = try request.supportedRecognitionLanguages()
let preferred = CommandLine.arguments.dropFirst(2).flatMap { $0.split(separator: ",").map(String.init) }
let languages = preferred.isEmpty ? ["en-US", "zh-Hans", "zh-Hant"] : preferred
let available = languages.filter { supported.contains($0) }
if available.isEmpty {
    throw NSError(domain: "No supported Vision recognition language", code: 1)
}
request.recognitionLanguages = available
if #available(macOS 13.0, *), preferred.isEmpty {
    request.automaticallyDetectsLanguage = true
}
let image = URL(fileURLWithPath: CommandLine.arguments[1])
try VNImageRequestHandler(url: image, options: [:]).perform([request])

let results = (request.results ?? []).compactMap { observation -> Label? in
    guard let candidate = observation.topCandidates(1).first else { return nil }
    let box = observation.boundingBox
    return Label(
        content: candidate.string,
        confidence: candidate.confidence,
        bbox: [box.minX, 1 - box.maxY, box.width, box.height]
    )
}
FileHandle.standardOutput.write(try JSONEncoder().encode(results))
