// Enumerate the GATT table of a BLE peripheral from the Mac, reading everything readable
// without pairing, to answer "is anything pollable without the device key?".
// Build: swiftc -O bleenum.swift -o bleenum
// Run:   ./bleenum [nameSubstring] [scanSeconds]
import Foundation
import CoreBluetooth

func hex(_ d: Data, _ max: Int = 24) -> String {
    let s = d.map { String(format: "%02x", $0) }.joined()
    return d.count > max ? String(s.prefix(max * 2)) + "..." : s
}

let want = CommandLine.arguments.count > 1 ? CommandLine.arguments[1].lowercased() : "inspire"
let secs = CommandLine.arguments.count > 2 ? Double(CommandLine.arguments[2])! : 15.0

final class Enum: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    var central: CBCentralManager!
    var found: [(CBPeripheral, Int, [String], String)] = []
    var target: CBPeripheral?
    var services: [CBService] = []

    func start() {
        central = CBCentralManager(delegate: self, queue: nil)
    }

    func centralManagerDidUpdateState(_ c: CBCentralManager) {
        guard c.state == .poweredOn else { print("adapter not ready: \(c.state.rawValue)"); return }
        print("scanning \(secs)s for \"\(want)\"...")
        c.scanForPeripherals(withServices: nil, options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
    }

    func centralManager(_ c: CBCentralManager, didDiscover p: CBPeripheral,
                        advertisementData d: [String: Any], rssi RSSI: NSNumber) {
        let name = (d[CBAdvertisementDataLocalNameKey] as? String) ?? p.name ?? ""
        var svcs: [String] = []
        if let u = d[CBAdvertisementDataServiceUUIDsKey] as? [CBUUID] { svcs = u.map { $0.uuidString } }
        var mfg = "-"
        if let m = d[CBAdvertisementDataManufacturerDataKey] as? Data { mfg = hex(m, 12) }
        if found.contains(where: { $0.0.identifier == p.identifier }) { return }
        found.append((p, RSSI.intValue, svcs, mfg))
        _ = name
    }

    func centralManager(_ c: CBCentralManager, didConnect p: CBPeripheral) {
        print("connected to \(p.name ?? "?"), discovering services")
        p.discoverServices(nil)
    }

    func centralManager(_ c: CBCentralManager, didFailToConnect p: CBPeripheral, error: Error?) {
        print("connect failed: \(error?.localizedDescription ?? "?")")
    }

    func peripheral(_ p: CBPeripheral, didDiscoverServices error: Error?) {
        if let e = error { print("services error: \(e.localizedDescription)") }
        services = p.services ?? []
        print("\nservices: \(services.count)")
        for s in services { print("  \(s.uuid.uuidString)") }
        for s in services { p.discoverCharacteristics(nil, for: s) }
    }

    func peripheral(_ p: CBPeripheral, didDiscoverCharacteristicsFor s: CBService, error: Error?) {
        print("\nservice \(s.uuid.uuidString)")
        for ch in s.characteristics ?? [] {
            print("  char \(ch.uuid.uuidString) props=\(ch.properties.rawValue)")
            if ch.properties.contains(.read) { p.readValue(for: ch) }
        }
    }

    func peripheral(_ p: CBPeripheral, didUpdateValueFor ch: CBCharacteristic, error: Error?) {
        if let v = ch.value {
            let ascii = String(data: v, encoding: .utf8) ?? ""
            print("    read \(ch.uuid.uuidString) = \(hex(v)) \(ascii.isEmpty ? "" : "|\(ascii.prefix(40))|")")
        } else if let e = error {
            print("    read \(ch.uuid.uuidString) failed: \(e.localizedDescription)")
        }
    }

    func dumpAll() {
        print("\n--- all peripherals: \(found.count) ---")
        for (p, r, s, m) in found.sorted(by: { $0.1 > $1.1 }) {
            let name = (p.name ?? "-").padding(toLength: 26, withPad: " ", startingAt: 0)
            print("  \(name) rssi=\(r) svc=\(s.joined(separator: ",")) mfg=\(m)")
        }
    }
}

let e = Enum()
e.start()
RunLoop.current.run(until: Date().addingTimeInterval(secs))
e.central.stopScan()
// pick a match by name or by the FD62 advertising service
var match: CBPeripheral?
for (p, r, svcs, _) in e.found.sorted(by: { $0.1 > $1.1 }) {
    let n = (p.name ?? "").lowercased()
    if n.contains(want) || svcs.contains(where: { $0.uppercased() == "FD62" }) {
        print("MATCH name=\(p.name ?? "-") rssi=\(r) svc=\(svcs)")
        match = p
        break
    }
}
if let m = match {
    m.delegate = e
    e.central.connect(m, options: nil)
    RunLoop.current.run(until: Date().addingTimeInterval(20))
} else {
    e.dumpAll()
}
