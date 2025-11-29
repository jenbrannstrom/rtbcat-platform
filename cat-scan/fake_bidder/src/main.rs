use axum::{routing::post, Json, Router};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use tokio::net::TcpListener;

/// Minimal OpenRTB-style structs (only what we need for now)

#[derive(Debug, Serialize, Deserialize)]
struct Banner {
    w: i32,
    h: i32,
}

#[derive(Debug, Serialize, Deserialize)]
struct Imp {
    id: String,
    #[serde(default)]
    banner: Option<Banner>,
    #[serde(default)]
    bidfloor: Option<f64>,
}

#[derive(Debug, Serialize, Deserialize)]
struct BidRequest {
    id: String,
    imp: Vec<Imp>,
}

#[derive(Debug, Serialize, Deserialize)]
struct Bid {
    id: String,
    impid: String,
    price: f64,
    adm: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct SeatBid {
    bid: Vec<Bid>,
}

#[derive(Debug, Serialize, Deserialize)]
struct BidResponse {
    id: String,
    seatbid: Vec<SeatBid>,
}

#[tokio::main]
async fn main() {
    // Build our application with a route
    let app = Router::new().route("/bid", post(handle_bid));

    // Listen on 0.0.0.0:3000
    let addr: SocketAddr = "0.0.0.0:3000".parse().unwrap();
    println!("fake_bidder listening on http://{}", addr);

    // Axum 0.7 style: use TcpListener + axum::serve
    let listener = TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

/// Very simple fake bidding logic:
/// - If first impression is 300x250 -> bid
/// - Otherwise -> no-bid (empty seatbid)
async fn handle_bid(Json(req): Json<BidRequest>) -> Json<BidResponse> {
    println!("Received request id={} with {} imps", req.id, req.imp.len());

    let mut seatbids: Vec<SeatBid> = Vec::new();

    if let Some(first_imp) = req.imp.first() {
        if let Some(banner) = &first_imp.banner {
            let should_bid = banner.w == 300 && banner.h == 250;

            if should_bid {
                let floor = first_imp.bidfloor.unwrap_or(0.5);
                let price = floor * 1.2_f64;

                let bid = Bid {
                    id: "bid-1".to_string(),
                    impid: first_imp.id.clone(),
                    price,
                    adm: "<div>Fake ad</div>".to_string(),
                };

                seatbids.push(SeatBid { bid: vec![bid] });
            }
        }
    }

    // If we never pushed a bid, seatbids will be empty = no-bid
    let resp = BidResponse {
        id: req.id,
        seatbid: seatbids,
    };

    Json(resp)
}
