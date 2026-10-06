/**
 * Backend API for Your-Own-AI.
 * Implements a highly optimized in-memory vector database using HNSW, KD-Trees, and Brute Force approaches,
 * wrapped in a C++ HTTP server (cpp-httplib) for seamless integration with Ollama embeddings.
 */
#ifdef _WIN32
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0A00
#endif
#include <windows.h>
#endif
#include "httplib.h"
#include <algorithm>
#include <chrono>
#include <climits>
#include <cmath>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <queue>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

using namespace std;
static const int DIMS = 16;

struct VectorItem {
  int id;
  string metadata;
  string category;
  vector<float> emb;
};
using DistFn = function<float(const vector<float> &,
                                   const vector<float> &)>;

float euclidean(const vector<float> &a, const vector<float> &b) {
  float s = 0;
  for (int i = 0; i < (int)a.size(); i++) {
    float d = a[i] - b[i];
    s += d * d;
  }
  return sqrt(s);
}

float cosine(const vector<float> &a, const vector<float> &b) {
  float dot = 0, na = 0, nb = 0;
  for (int i = 0; i < (int)a.size(); i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  if (na < 1e-9f || nb < 1e-9f)
    return 1.0f;
  return 1.0f - dot / (sqrt(na) * sqrt(nb));
}
float manhattan(const vector<float> &a, const vector<float> &b) {
  float s = 0;
  for (int i = 0; i < (int)a.size(); i++)
    s += abs(a[i] - b[i]);
  return s;
}
DistFn getDistFn(const string &m) {
  if (m == "cosine")
    return cosine;
  if (m == "manhattan")
    return manhattan;
  return euclidean;
}
class BruteForce {
public:
  vector<VectorItem> items;
  void insert(const VectorItem &v) { items.push_back(v); }
  vector<pair<float, int>> knn(const vector<float> &q, int k,
                                         DistFn dist) {
    vector<pair<float, int>> r;
    r.reserve(items.size());
    for (auto &v : items)
      r.push_back({dist(q, v.emb), v.id});
    sort(r.begin(), r.end());
    if ((int)r.size() > k)
      r.resize(k);
    return r;
  }
  void remove(int id) {
    items.erase(
        remove_if(items.begin(), items.end(),
                       [id](const VectorItem &v) { return v.id == id; }),
        items.end());
  }
};
struct KDNode {
  VectorItem item;
  KDNode *left = nullptr;
  KDNode *right = nullptr;
  explicit KDNode(const VectorItem &v) : item(v) {}
};

class KDTree {
  KDNode *root = nullptr;
  int dims;
  void destroy(KDNode *n) {
    if (!n)
      return;
    destroy(n->left);
    destroy(n->right);
    delete n;
  }
  KDNode *ins(KDNode *n, const VectorItem &v, int d) {
    if (!n)
      return new KDNode(v);
    int ax = d % dims;
    if (v.emb[ax] < n->item.emb[ax])
      n->left = ins(n->left, v, d + 1);
    else
      n->right = ins(n->right, v, d + 1);
    return n;
  }
  void knn(KDNode *n, const vector<float> &q, int k, int d, DistFn dist,
           priority_queue<pair<float, int>> &heap) {
    if (!n)
      return;
    float dn = dist(q, n->item.emb);
    if ((int)heap.size() < k || dn < heap.top().first) {
      heap.push({dn, n->item.id});
      if ((int)heap.size() > k)
        heap.pop();
    }
    int ax = d % dims;
    float diff = q[ax] - n->item.emb[ax];
    KDNode *closer = diff < 0 ? n->left : n->right;
    KDNode *farther = diff < 0 ? n->right : n->left;
    knn(closer, q, k, d + 1, dist, heap);
    if ((int)heap.size() < k || abs(diff) < heap.top().first)
      knn(farther, q, k, d + 1, dist, heap);
  }

public:
  explicit KDTree(int d) : dims(d) {}
  ~KDTree() { destroy(root); }
  void insert(const VectorItem &v) { root = ins(root, v, 0); }
  vector<pair<float, int>> knn(const vector<float> &q, int k,
                                         DistFn dist) {
    priority_queue<pair<float, int>> heap;
    knn(root, q, k, 0, dist, heap);
    vector<pair<float, int>> r;
    while (!heap.empty()) {
      r.push_back(heap.top());
      heap.pop();
    }
    sort(r.begin(), r.end());
    return r;
  }
  void rebuild(const vector<VectorItem> &items) {
    destroy(root);
    root = nullptr;
    for (auto &v : items)
      insert(v);
  }
};

class HNSW {
  struct Node {
    VectorItem item;
    int maxLyr;
    vector<vector<int>> nbrs;
  };
  unordered_map<int, Node> G;
  int M, M0, ef_build;
  float mL;
  int topLayer = -1;
  int entryPt = -1;
  mt19937 rng;
  int randLevel() {
    uniform_real_distribution<float> u(0.0f, 1.0f);
    return (int)floor(-log(u(rng)) * mL);
  }
  vector<pair<float, int>> searchLayer(const vector<float> &q,
                                                 int ep, int ef, int lyr,
                                                 DistFn dist) {
    unordered_map<int, bool> vis;
    priority_queue<pair<float, int>,
                        vector<pair<float, int>>, greater<>>
        cands;
    priority_queue<pair<float, int>> found;
    float d0 = dist(q, G[ep].item.emb);
    vis[ep] = true;
    cands.push({d0, ep});
    found.push({d0, ep});
    while (!cands.empty()) {
      auto [cd, cid] = cands.top();
      cands.pop();
      if ((int)found.size() >= ef && cd > found.top().first)
        break;
      if (lyr >= (int)G[cid].nbrs.size())
        continue;
      for (int nid : G[cid].nbrs[lyr]) {
        if (vis[nid] || !G.count(nid))
          continue;
        vis[nid] = true;
        float nd = dist(q, G[nid].item.emb);
        if ((int)found.size() < ef || nd < found.top().first) {
          cands.push({nd, nid});
          found.push({nd, nid});
          if ((int)found.size() > ef)
            found.pop();
        }
      }
    }
    vector<pair<float, int>> res;
    while (!found.empty()) {
      res.push_back(found.top());
      found.pop();
    }
    sort(res.begin(), res.end());
    return res;
  }
  vector<int> selectNbrs(vector<pair<float, int>> &cands,
                              int maxM) {
    vector<int> r;
    for (int i = 0; i < min((int)cands.size(), maxM); i++)
      r.push_back(cands[i].second);
    return r;
  }

public:
  HNSW(int m = 16, int efBuild = 200)
      : M(m), M0(2 * m), ef_build(efBuild), mL(1.0f / log((float)m)),
        rng(42) {}
  void insert(const VectorItem &item, DistFn dist) {
    int id = item.id;
    int lvl = randLevel();
    G[id] = {item, lvl, vector<vector<int>>(lvl + 1)};
    if (entryPt == -1) {
      entryPt = id;
      topLayer = lvl;
      return;
    }
    int ep = entryPt;
    for (int lc = topLayer; lc > lvl; lc--) {
      if (lc < (int)G[ep].nbrs.size()) {
        auto W = searchLayer(item.emb, ep, 1, lc, dist);
        if (!W.empty())
          ep = W[0].second;
      }
    }
    for (int lc = min(topLayer, lvl); lc >= 0; lc--) {
      auto W = searchLayer(item.emb, ep, ef_build, lc, dist);
      int maxM = (lc == 0) ? M0 : M;
      auto sel = selectNbrs(W, maxM);
      G[id].nbrs[lc] = sel;
      for (int nid : sel) {
        if (!G.count(nid))
          continue;
        if ((int)G[nid].nbrs.size() <= lc)
          G[nid].nbrs.resize(lc + 1);
        auto &conn = G[nid].nbrs[lc];
        conn.push_back(id);
        if ((int)conn.size() > maxM) {
          vector<pair<float, int>> ds;
          for (int c : conn)
            if (G.count(c))
              ds.push_back({dist(G[nid].item.emb, G[c].item.emb), c});
          sort(ds.begin(), ds.end());
          conn.clear();
          for (int i = 0; i < maxM && i < (int)ds.size(); i++)
            conn.push_back(ds[i].second);
        }
      }
      if (!W.empty())
        ep = W[0].second;
    }
    if (lvl > topLayer) {
      topLayer = lvl;
      entryPt = id;
    }
  }
  vector<pair<float, int>> knn(const vector<float> &q, int k,
                                         int ef, DistFn dist) {
    if (entryPt == -1)
      return {};
    int ep = entryPt;
    for (int lc = topLayer; lc > 0; lc--) {
      if (lc < (int)G[ep].nbrs.size()) {
        auto W = searchLayer(q, ep, 1, lc, dist);
        if (!W.empty())
          ep = W[0].second;
      }
    }
    auto W = searchLayer(q, ep, max(ef, k), 0, dist);
    if ((int)W.size() > k)
      W.resize(k);
    return W;
  }
  void remove(int id) {
    if (!G.count(id))
      return;
    for (auto &[nid, nd] : G)
      for (auto &layer : nd.nbrs)
        layer.erase(std::remove(layer.begin(), layer.end(), id), layer.end());
    if (entryPt == id) {
      entryPt = -1;
      for (auto &[nid, nd] : G)
        if (nid != id) {
          entryPt = nid;
          break;
        }
    }
    G.erase(id);
  }
  struct GraphInfo {
    int topLayer, nodeCount;
    vector<int> nodesPerLayer, edgesPerLayer;
    struct NV {
      int id;
      string metadata, category;
      int maxLyr;
    };
    struct EV {
      int src, dst, lyr;
    };
    vector<NV> nodes;
    vector<EV> edges;
  };
  GraphInfo getInfo() {
    GraphInfo gi;
    gi.topLayer = topLayer;
    gi.nodeCount = (int)G.size();
    int maxL = max(topLayer + 1, 1);
    gi.nodesPerLayer.assign(maxL, 0);
    gi.edgesPerLayer.assign(maxL, 0);
    for (auto &[id, nd] : G) {
      gi.nodes.push_back({id, nd.item.metadata, nd.item.category, nd.maxLyr});
      for (int lc = 0; lc <= nd.maxLyr && lc < maxL; lc++) {
        gi.nodesPerLayer[lc]++;
        if (lc < (int)nd.nbrs.size())
          for (int nid : nd.nbrs[lc])
            if (id < nid) {
              gi.edgesPerLayer[lc]++;
              gi.edges.push_back({id, nid, lc});
            }
      }
    }
    return gi;
  }
  size_t size() const { return G.size(); }
};

class VectorDB {
  unordered_map<int, VectorItem> store;
  BruteForce bf;
  KDTree kdt;
  HNSW hnsw;
  mutex mu;
  int nextId = 1;

public:
  const int dims;
  explicit VectorDB(int d) : kdt(d), hnsw(16, 200), dims(d) {}
  int insert(const string &meta, const string &cat,
             const vector<float> &emb, DistFn dist) {
    lock_guard<mutex> lk(mu);
    VectorItem v{nextId++, meta, cat, emb};
    store[v.id] = v;
    bf.insert(v);
    kdt.insert(v);
    hnsw.insert(v, dist);
    return v.id;
  }
  bool remove(int id) {
    lock_guard<mutex> lk(mu);
    if (!store.count(id))
      return false;
    store.erase(id);
    bf.remove(id);
    hnsw.remove(id);
    vector<VectorItem> rem;
    for (auto &[i, v] : store)
      rem.push_back(v);
    kdt.rebuild(rem);
    return true;
  }
  struct Hit {
    int id;
    string meta, cat;
    vector<float> emb;
    float dist;
  };
  struct SearchOut {
    vector<Hit> hits;
    long long us;
    string algo, metric;
  };
  SearchOut search(const vector<float> &q, int k,
                   const string &metric, const string &algo) {
    lock_guard<mutex> lk(mu);
    auto dfn = getDistFn(metric);
    auto t0 = chrono::high_resolution_clock::now();
    vector<pair<float, int>> raw;
    if (algo == "bruteforce")
      raw = bf.knn(q, k, dfn);
    else if (algo == "kdtree")
      raw = kdt.knn(q, k, dfn);
    else
      raw = hnsw.knn(q, k, 50, dfn);
    long long us = chrono::duration_cast<chrono::microseconds>(
                       chrono::high_resolution_clock::now() - t0)
                       .count();
    SearchOut out;
    out.us = us;
    out.algo = algo;
    out.metric = metric;
    for (auto &[d, id] : raw)
      if (store.count(id))
        out.hits.push_back(
            {id, store[id].metadata, store[id].category, store[id].emb, d});
    return out;
  }
  struct BenchOut {
    long long bfUs, kdUs, hnswUs;
    int n;
  };
  BenchOut benchmark(const vector<float> &q, int k,
                     const string &metric) {
    lock_guard<mutex> lk(mu);
    auto dfn = getDistFn(metric);
    auto time = [&](auto fn) -> long long {
      auto t = chrono::high_resolution_clock::now();
      fn();
      return chrono::duration_cast<chrono::microseconds>(
                 chrono::high_resolution_clock::now() - t)
          .count();
    };
    return {time([&] { bf.knn(q, k, dfn); }), time([&] { kdt.knn(q, k, dfn); }),
            time([&] { hnsw.knn(q, k, 50, dfn); }), (int)store.size()};
  }
  vector<VectorItem> all() {
    lock_guard<mutex> lk(mu);
    vector<VectorItem> r;
    for (auto &[id, v] : store)
      r.push_back(v);
    return r;
  }
  HNSW::GraphInfo hnswInfo() {
    lock_guard<mutex> lk(mu);
    return hnsw.getInfo();
  }
  size_t size() {
    lock_guard<mutex> lk(mu);
    return store.size();
  }
};
string jS(const string &s) {
  string o = "\"";
  for (char c : s) {
    if (c == '"')
      o += "\\\"";
    else if (c == '\\')
      o += "\\\\";
    else if (c == '\n')
      o += "\\n";
    else if (c == '\r')
      o += "\\r";
    else if (c == '\t')
      o += "\\t";
    else
      o += c;
  }
  return o + '"';
}
string jVec(const vector<float> &v) {
  ostringstream ss;
  ss << '[';
  for (size_t i = 0; i < v.size(); i++) {
    if (i)
      ss << ',';
    ss << fixed << setprecision(4) << v[i];
  }
  return ss.str() + ']';
}
vector<float> parseVec(const string &s) {
  vector<float> v;
  istringstream ss(s);
  string t;
  while (getline(ss, t, ','))
    try {
      v.push_back(stof(t));
    } catch (...) {
    }
  return v;
}
string extractStr(const string &body, const string &key) {
  size_t p = body.find('"' + key + '"');
  if (p == string::npos)
    return "";
  p = body.find(':', p) + 1;
  while (p < body.size() && (body[p] == ' ' || body[p] == '\t'))
    p++;
  if (p >= body.size() || body[p] != '"')
    return "";
  p++;
  string result;
  while (p < body.size()) {
    if (body[p] == '"')
      break;
    if (body[p] == '\\' && p + 1 < body.size()) {
      p++;
      switch (body[p]) {
      case '"':
        result += '"';
        break;
      case '\\':
        result += '\\';
        break;
      case 'n':
        result += '\n';
        break;
      case 'r':
        result += '\r';
        break;
      case 't':
        result += '\t';
        break;
      default:
        result += body[p];
        break;
      }
    } else {
      result += body[p];
    }
    p++;
  }
  return result;
}
int extractInt(const string &body, const string &key, int def = 0) {
  size_t p = body.find('"' + key + '"');
  if (p == string::npos)
    return def;
  p = body.find(':', p) + 1;
  while (p < body.size() && (body[p] == ' ' || body[p] == '\t'))
    p++;
  try {
    return stoi(body.substr(p));
  } catch (...) {
    return def;
  }
}
bool parseBody(const string &b, string &meta, string &cat,
               vector<float> &emb) {
  meta = extractStr(b, "metadata");
  cat = extractStr(b, "category");
  auto extractArr = [&](const string &key) -> vector<float> {
    size_t p = b.find('"' + key + '"');
    if (p == string::npos)
      return {};
    p = b.find('[', p);
    if (p == string::npos)
      return {};
    size_t e = b.find(']', p);
    if (e == string::npos)
      return {};
    return parseVec(b.substr(p + 1, e - p - 1));
  };
  emb = extractArr("embedding");
  return !meta.empty() && !emb.empty();
}
void cors(httplib::Response &res) {
  res.set_header("Access-Control-Allow-Origin", "*");
  res.set_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS");
  res.set_header("Access-Control-Allow-Headers", "Content-Type");
}
vector<string> chunkText(const string &text,
                                   int chunkWords = 250,
                                   int overlapWords = 30) {
  istringstream ss(text);
  vector<string> words;
  string w;
  while (ss >> w)
    words.push_back(w);
  if (words.empty())
    return {};
  if ((int)words.size() <= chunkWords)
    return {text};
  vector<string> chunks;
  int step = chunkWords - overlapWords;
  for (int i = 0; i < (int)words.size(); i += step) {
    int end = min(i + chunkWords, (int)words.size());
    string chunk;
    for (int j = i; j < end; j++) {
      if (j > i)
        chunk += ' ';
      chunk += words[j];
    }
    chunks.push_back(chunk);
    if (end == (int)words.size())
      break;
  }
  return chunks;
}

class OllamaClient {
  string host;
  int port;
  string esc(const string &s) {
    string o;
    for (char c : s) {
      if (c == '"')
        o += "\\\"";
      else if (c == '\\')
        o += "\\\\";
      else if (c == '\n')
        o += "\\n";
      else if (c == '\r')
        o += "\\r";
      else if (c == '\t')
        o += "\\t";
      else
        o += c;
    }
    return o;
  }
  vector<float> parseEmbedding(const string &body) {
    size_t p = body.find("\"embedding\"");
    if (p == string::npos)
      return {};
    p = body.find('[', p);
    if (p == string::npos)
      return {};
    size_t e = p + 1, depth = 1;
    while (e < body.size() && depth > 0) {
      if (body[e] == '[')
        depth++;
      else if (body[e] == ']')
        depth--;
      e++;
    }
    return parseVec(body.substr(p + 1, e - p - 2));
  }
  string parseResponse(const string &body) {
    return extractStr(body, "response");
  }

public:
  string embedModel = "nomic-embed-text";
  string genModel = "llama3.2:1b";
  OllamaClient(const string &h = "127.0.0.1", int p = 11434)
      : host(h), port(p) {}
  bool isAvailable() {
    httplib::Client cli(host, port);
    cli.set_connection_timeout(2, 0);
    auto res = cli.Get("/api/tags");
    return res && res->status == 200;
  }
  vector<float> embed(const string &text) {
    httplib::Client cli(host, port);
    cli.set_connection_timeout(3, 0);
    cli.set_read_timeout(30, 0);
    string body =
        "{\"model\":\"" + embedModel + "\",\"prompt\":\"" + esc(text) + "\"}";
    auto res = cli.Post("/api/embeddings", body, "application/json");
    if (!res || res->status != 200)
      return {};
    return parseEmbedding(res->body);
  }
  string generate(const string &prompt) {
    httplib::Client cli(host, port);
    cli.set_connection_timeout(3, 0);
    cli.set_read_timeout(180, 0);
    string body = "{\"model\":\"" + genModel +
                       "\","
                       "\"prompt\":\"" +
                       esc(prompt) +
                       "\","
                       "\"stream\":false}";
    auto res = cli.Post("/api/generate", body, "application/json");
    if (!res || res->status != 200)
      return "ERROR: Ollama unavailable. Run: ollama serve";
    return parseResponse(res->body);
  }
};
struct DocItem {
  int id;
  string title;
  string text;
  vector<float> emb;
};

class DocumentDB {
  unordered_map<int, DocItem> store;
  HNSW hnsw;
  BruteForce bf;
  mutex mu;
  int nextId = 1;
  int dims = 0;

public:
  DocumentDB() : hnsw(16, 200) {}
  int insert(const string &title, const string &text,
             const vector<float> &emb) {
    lock_guard<mutex> lk(mu);
    if (dims == 0)
      dims = (int)emb.size();
    DocItem item{nextId++, title, text, emb};
    store[item.id] = item;
    VectorItem vi{item.id, title, "doc", emb};
    hnsw.insert(vi, cosine);
    bf.insert(vi);
    return item.id;
  }
  vector<pair<float, DocItem>> search(const vector<float> &q,
                                                int k, float max_dist = 0.7f) {
    lock_guard<mutex> lk(mu);
    if (store.empty())
      return {};
    auto raw =
        (store.size() < 10) ? bf.knn(q, k, cosine) : hnsw.knn(q, k, 50, cosine);
    vector<pair<float, DocItem>> out;
    for (auto &[d, id] : raw)
      if (store.count(id) && d <= max_dist)
        out.push_back({d, store[id]});
    return out;
  }
  bool remove(int id) {
    lock_guard<mutex> lk(mu);
    if (!store.count(id))
      return false;
    store.erase(id);
    hnsw.remove(id);
    bf.remove(id);
    return true;
  }
  vector<DocItem> all() {
    lock_guard<mutex> lk(mu);
    vector<DocItem> r;
    for (auto &[id, v] : store)
      r.push_back(v);
    return r;
  }
  size_t size() {
    lock_guard<mutex> lk(mu);
    return store.size();
  }
  int getDims() { return dims; }
};
void loadDemo(VectorDB &db) {
  auto dist = getDistFn("cosine");
  db.insert("Linked List: nodes connected by pointers", "cs",
            {0.90f, 0.85f, 0.72f, 0.68f, 0.12f, 0.08f, 0.15f, 0.10f, 0.05f,
             0.08f, 0.06f, 0.09f, 0.07f, 0.11f, 0.08f, 0.06f},
            dist);
  db.insert("Binary Search Tree: O(log n) search and insert", "cs",
            {0.88f, 0.82f, 0.78f, 0.74f, 0.15f, 0.10f, 0.08f, 0.12f, 0.06f,
             0.07f, 0.08f, 0.05f, 0.09f, 0.06f, 0.07f, 0.10f},
            dist);
  db.insert("Dynamic Programming: memoization overlapping subproblems", "cs",
            {0.82f, 0.76f, 0.88f, 0.80f, 0.20f, 0.18f, 0.12f, 0.09f, 0.07f,
             0.06f, 0.08f, 0.07f, 0.08f, 0.09f, 0.06f, 0.07f},
            dist);
  db.insert("Graph BFS and DFS: breadth and depth first traversal", "cs",
            {0.85f, 0.80f, 0.75f, 0.82f, 0.18f, 0.14f, 0.10f, 0.08f, 0.06f,
             0.09f, 0.07f, 0.06f, 0.10f, 0.08f, 0.09f, 0.07f},
            dist);
  db.insert("Hash Table: O(1) lookup with collision chaining", "cs",
            {0.87f, 0.78f, 0.70f, 0.76f, 0.13f, 0.11f, 0.09f, 0.14f, 0.08f,
             0.07f, 0.06f, 0.08f, 0.07f, 0.10f, 0.08f, 0.09f},
            dist);
  db.insert("Calculus: derivatives integrals and limits", "math",
            {0.12f, 0.15f, 0.18f, 0.10f, 0.91f, 0.86f, 0.78f, 0.72f, 0.08f,
             0.06f, 0.07f, 0.09f, 0.07f, 0.08f, 0.06f, 0.10f},
            dist);
  db.insert("Linear Algebra: matrices eigenvalues eigenvectors", "math",
            {0.20f, 0.18f, 0.15f, 0.12f, 0.88f, 0.90f, 0.82f, 0.76f, 0.09f,
             0.07f, 0.08f, 0.06f, 0.10f, 0.07f, 0.08f, 0.09f},
            dist);
  db.insert("Probability: distributions random variables Bayes theorem", "math",
            {0.15f, 0.12f, 0.20f, 0.18f, 0.84f, 0.80f, 0.88f, 0.82f, 0.07f,
             0.08f, 0.06f, 0.10f, 0.09f, 0.06f, 0.09f, 0.08f},
            dist);
  db.insert("Number Theory: primes modular arithmetic RSA cryptography", "math",
            {0.22f, 0.16f, 0.14f, 0.20f, 0.80f, 0.85f, 0.76f, 0.90f, 0.08f,
             0.09f, 0.07f, 0.06f, 0.08f, 0.10f, 0.07f, 0.06f},
            dist);
  db.insert("Combinatorics: permutations combinations generating functions",
            "math",
            {0.18f, 0.20f, 0.16f, 0.14f, 0.86f, 0.78f, 0.84f, 0.80f, 0.06f,
             0.07f, 0.09f, 0.08f, 0.06f, 0.09f, 0.10f, 0.07f},
            dist);
  db.insert("Neapolitan Pizza: wood-fired dough San Marzano tomatoes", "food",
            {0.08f, 0.06f, 0.09f, 0.07f, 0.07f, 0.08f, 0.06f, 0.09f, 0.90f,
             0.86f, 0.78f, 0.72f, 0.08f, 0.06f, 0.09f, 0.07f},
            dist);
  db.insert("Sushi: vinegared rice raw fish and nori rolls", "food",
            {0.06f, 0.08f, 0.07f, 0.09f, 0.09f, 0.06f, 0.08f, 0.07f, 0.86f,
             0.90f, 0.82f, 0.76f, 0.07f, 0.09f, 0.06f, 0.08f},
            dist);
  db.insert("Ramen: noodle soup with chashu pork and soft-boiled eggs", "food",
            {0.09f, 0.07f, 0.06f, 0.08f, 0.08f, 0.09f, 0.07f, 0.06f, 0.82f,
             0.78f, 0.90f, 0.84f, 0.09f, 0.07f, 0.08f, 0.06f},
            dist);
  db.insert("Tacos: corn tortillas with carnitas salsa and cilantro", "food",
            {0.07f, 0.09f, 0.08f, 0.06f, 0.06f, 0.07f, 0.09f, 0.08f, 0.78f,
             0.82f, 0.86f, 0.90f, 0.06f, 0.08f, 0.07f, 0.09f},
            dist);
  db.insert("Croissant: laminated pastry with buttery flaky layers", "food",
            {0.06f, 0.07f, 0.10f, 0.09f, 0.10f, 0.06f, 0.07f, 0.10f, 0.85f,
             0.80f, 0.76f, 0.82f, 0.09f, 0.07f, 0.10f, 0.06f},
            dist);
  db.insert("Basketball: fast-paced shooting dribbling slam dunks", "sports",
            {0.09f, 0.07f, 0.08f, 0.10f, 0.08f, 0.09f, 0.07f, 0.06f, 0.08f,
             0.07f, 0.09f, 0.06f, 0.91f, 0.85f, 0.78f, 0.72f},
            dist);
  db.insert("Football: tackles touchdowns field goals and strategy", "sports",
            {0.07f, 0.09f, 0.06f, 0.08f, 0.09f, 0.07f, 0.10f, 0.08f, 0.07f,
             0.09f, 0.08f, 0.07f, 0.87f, 0.89f, 0.82f, 0.76f},
            dist);
  db.insert("Tennis: racket volleys groundstrokes and Wimbledon serves",
            "sports",
            {0.08f, 0.06f, 0.09f, 0.07f, 0.07f, 0.08f, 0.06f, 0.09f, 0.09f,
             0.06f, 0.07f, 0.08f, 0.83f, 0.80f, 0.88f, 0.82f},
            dist);
  db.insert("Chess: openings endgames tactics strategic board game", "sports",
            {0.25f, 0.20f, 0.22f, 0.18f, 0.22f, 0.18f, 0.20f, 0.15f, 0.06f,
             0.08f, 0.07f, 0.09f, 0.80f, 0.84f, 0.78f, 0.90f},
            dist);
  db.insert("Swimming: butterfly freestyle backstroke Olympic competition",
            "sports",
            {0.06f, 0.08f, 0.07f, 0.09f, 0.08f, 0.06f, 0.09f, 0.07f, 0.10f,
             0.08f, 0.06f, 0.07f, 0.85f, 0.82f, 0.86f, 0.80f},
            dist);
}
int main() {
  VectorDB db(DIMS);
  DocumentDB docDB;
  OllamaClient ollama;
  loadDemo(db);
  bool ollamaUp = ollama.isAvailable();
  cout << "=== VectorDB Engine ===" << endl;
  cout << "http://localhost:8080" << endl;
  cout << db.size() << " demo vectors | " << DIMS
            << " dims | HNSW+KD-Tree+BruteForce" << endl;
  cout << "Ollama: "
            << (ollamaUp ? "ONLINE" : "OFFLINE (install from ollama.com)")
            << endl;
  if (ollamaUp)
    cout << "  embed model: " << ollama.embedModel
              << "  gen model: " << ollama.genModel << endl;
  httplib::Server svr;
  svr.Options(".*", [](const httplib::Request &, httplib::Response &res) {
    cors(res);
    res.status = 204;
  });
  svr.Get("/search", [&](const httplib::Request &req, httplib::Response &res) {
    cors(res);
    auto q = parseVec(req.get_param_value("v"));
    if ((int)q.size() != DIMS) {
      res.set_content("{\"error\":\"need " + to_string(DIMS) +
                          "D vector\"}",
                      "application/json");
      return;
    }
    int k = 5;
    try {
      k = stoi(req.get_param_value("k"));
    } catch (...) {
    }
    auto metric = req.get_param_value("metric");
    if (metric.empty())
      metric = "cosine";
    auto algo = req.get_param_value("algo");
    if (algo.empty())
      algo = "hnsw";
    auto out = db.search(q, k, metric, algo);
    ostringstream ss;
    ss << "{\"results\":[";
    for (size_t i = 0; i < out.hits.size(); i++) {
      if (i)
        ss << ',';
      auto &h = out.hits[i];
      ss << "{\"id\":" << h.id << ",\"metadata\":" << jS(h.meta)
         << ",\"category\":" << jS(h.cat) << ",\"distance\":" << fixed
         << setprecision(6) << h.dist << ",\"embedding\":" << jVec(h.emb)
         << '}';
    }
    ss << "],\"latencyUs\":" << out.us << ",\"algo\":" << jS(out.algo)
       << ",\"metric\":" << jS(out.metric) << '}';
    res.set_content(ss.str(), "application/json");
  });
  svr.Post("/insert", [&](const httplib::Request &req, httplib::Response &res) {
    cors(res);
    string meta, cat;
    vector<float> emb;
    if (!parseBody(req.body, meta, cat, emb) || (int)emb.size() != DIMS) {
      res.set_content("{\"error\":\"invalid body\"}", "application/json");
      return;
    }
    int id = db.insert(meta, cat, emb, getDistFn("cosine"));
    res.set_content("{\"id\":" + to_string(id) + "}", "application/json");
  });
  svr.Delete(R"(/delete/(\d+))", [&](const httplib::Request &req,
                                     httplib::Response &res) {
    cors(res);
    int id = stoi(req.matches[1]);
    bool ok = db.remove(id);
    res.set_content("{\"ok\":" + string(ok ? "true" : "false") + "}",
                    "application/json");
  });
  svr.Get("/items", [&](const httplib::Request &, httplib::Response &res) {
    cors(res);
    auto items = db.all();
    ostringstream ss;
    ss << '[';
    for (size_t i = 0; i < items.size(); i++) {
      if (i)
        ss << ',';
      auto &v = items[i];
      ss << "{\"id\":" << v.id << ",\"metadata\":" << jS(v.metadata)
         << ",\"category\":" << jS(v.category)
         << ",\"embedding\":" << jVec(v.emb) << '}';
    }
    ss << ']';
    res.set_content(ss.str(), "application/json");
  });
  svr.Get("/benchmark",
          [&](const httplib::Request &req, httplib::Response &res) {
            cors(res);
            auto q = parseVec(req.get_param_value("v"));
            if ((int)q.size() != DIMS) {
              res.set_content("{\"error\":\"need " + to_string(DIMS) +
                                  "D vector\"}",
                              "application/json");
              return;
            }
            int k = 5;
            try {
              k = stoi(req.get_param_value("k"));
            } catch (...) {
            }
            auto metric = req.get_param_value("metric");
            if (metric.empty())
              metric = "cosine";
            auto b = db.benchmark(q, k, metric);
            ostringstream ss;
            ss << "{\"bruteforceUs\":" << b.bfUs << ",\"kdtreeUs\":" << b.kdUs
               << ",\"hnswUs\":" << b.hnswUs << ",\"itemCount\":" << b.n << '}';
            res.set_content(ss.str(), "application/json");
          });
  svr.Get("/hnsw-info", [&](const httplib::Request &, httplib::Response &res) {
    cors(res);
    auto gi = db.hnswInfo();
    ostringstream ss;
    ss << "{\"topLayer\":" << gi.topLayer << ",\"nodeCount\":" << gi.nodeCount
       << ",\"nodesPerLayer\":[";
    for (size_t i = 0; i < gi.nodesPerLayer.size(); i++) {
      if (i)
        ss << ',';
      ss << gi.nodesPerLayer[i];
    }
    ss << "],\"edgesPerLayer\":[";
    for (size_t i = 0; i < gi.edgesPerLayer.size(); i++) {
      if (i)
        ss << ',';
      ss << gi.edgesPerLayer[i];
    }
    ss << "],\"nodes\":[";
    for (size_t i = 0; i < gi.nodes.size(); i++) {
      if (i)
        ss << ',';
      auto &n = gi.nodes[i];
      ss << "{\"id\":" << n.id << ",\"metadata\":" << jS(n.metadata)
         << ",\"category\":" << jS(n.category) << ",\"maxLyr\":" << n.maxLyr
         << '}';
    }
    ss << "],\"edges\":[";
    for (size_t i = 0; i < gi.edges.size(); i++) {
      if (i)
        ss << ',';
      auto &e = gi.edges[i];
      ss << "{\"src\":" << e.src << ",\"dst\":" << e.dst << ",\"lyr\":" << e.lyr
         << '}';
    }
    ss << "]}";
    res.set_content(ss.str(), "application/json");
  });
  svr.Post(
      "/doc/insert", [&](const httplib::Request &req, httplib::Response &res) {
        cors(res);
        auto title = extractStr(req.body, "title");
        auto text = extractStr(req.body, "text");
        if (title.empty() || text.empty()) {
          res.set_content("{\"error\":\"need title and text\"}",
                          "application/json");
          return;
        }
        auto chunks = chunkText(text, 250, 30);
        vector<int> ids;
        for (int i = 0; i < (int)chunks.size(); i++) {
          auto emb = ollama.embed(chunks[i]);
          if (emb.empty()) {
            res.set_content(
                "{\"error\":\"Ollama unavailable. "
                "Install from https://ollama.com then run: "
                "ollama pull nomic-embed-text && ollama pull llama3.2:1b\"}",
                "application/json");
            return;
          }
          string chunkTitle =
              (chunks.size() > 1) ? title + " [" + to_string(i + 1) + "/" +
                                        to_string(chunks.size()) + "]"
                                  : title;
          ids.push_back(docDB.insert(chunkTitle, chunks[i], emb));
        }
        ostringstream ss;
        ss << "{\"ids\":[";
        for (size_t i = 0; i < ids.size(); i++) {
          if (i)
            ss << ',';
          ss << ids[i];
        }
        ss << "],\"chunks\":" << chunks.size()
           << ",\"dims\":" << docDB.getDims() << '}';
        res.set_content(ss.str(), "application/json");
      });
  svr.Delete(R"(/doc/delete/(\d+))", [&](const httplib::Request &req,
                                         httplib::Response &res) {
    cors(res);
    int id = stoi(req.matches[1]);
    bool ok = docDB.remove(id);
    res.set_content("{\"ok\":" + string(ok ? "true" : "false") + "}",
                    "application/json");
  });
  svr.Get("/doc/list", [&](const httplib::Request &, httplib::Response &res) {
    cors(res);
    auto docs = docDB.all();
    ostringstream ss;
    ss << '[';
    for (size_t i = 0; i < docs.size(); i++) {
      if (i)
        ss << ',';
      string preview = docs[i].text.substr(0, 120);
      if (docs[i].text.size() > 120)
        preview += "…";
      ss << "{\"id\":" << docs[i].id << ",\"title\":" << jS(docs[i].title)
         << ",\"preview\":" << jS(preview) << ",\"words\":"
         << (int)count(docs[i].text.begin(), docs[i].text.end(), ' ') + 1
         << '}';
    }
    ss << ']';
    res.set_content(ss.str(), "application/json");
  });
  svr.Post("/doc/search", [&](const httplib::Request &req,
                              httplib::Response &res) {
    cors(res);
    auto question = extractStr(req.body, "question");
    int k = extractInt(req.body, "k", 3);
    if (question.empty()) {
      res.set_content("{\"error\":\"need question\"}", "application/json");
      return;
    }
    auto qEmb = ollama.embed(question);
    if (qEmb.empty()) {
      res.set_content("{\"error\":\"Ollama unavailable\"}", "application/json");
      return;
    }
    auto hits = docDB.search(qEmb, k);
    ostringstream ss;
    ss << "{\"contexts\":[";
    for (size_t i = 0; i < hits.size(); i++) {
      if (i)
        ss << ',';
      ss << "{\"id\":" << hits[i].second.id
         << ",\"title\":" << jS(hits[i].second.title)
         << ",\"distance\":" << fixed << setprecision(4)
         << hits[i].first << '}';
    }
    ss << "]}";
    res.set_content(ss.str(), "application/json");
  });
  svr.Post("/doc/ask", [&](const httplib::Request &req,
                           httplib::Response &res) {
    cors(res);
    auto question = extractStr(req.body, "question");
    int k = extractInt(req.body, "k", 3);
    if (question.empty()) {
      res.set_content("{\"error\":\"need question\"}", "application/json");
      return;
    }
    auto qEmb = ollama.embed(question);
    if (qEmb.empty()) {
      res.set_content("{\"error\":\"Ollama unavailable\"}", "application/json");
      return;
    }
    auto hits = docDB.search(qEmb, k);
    ostringstream ctx;
    for (int i = 0; i < (int)hits.size(); i++) {
      ctx << "[" << (i + 1) << "] " << hits[i].second.title << ":\n"
          << hits[i].second.text << "\n\n";
    }
    string prompt =
        "You are a helpful assistant. Answer the user's question directly. "
        "Use the provided context if it contains relevant information. "
        "If it doesn't, just use your own general knowledge. "
        "IMPORTANT: Do NOT mention the 'context', 'provided text', or say "
        "things like 'the context doesn't mention'. "
        "Just answer the question naturally.\n\n"
        "Context:\n" +
        ctx.str() + "Question: " + question +
        "\n\n"
        "Answer:";
    auto answer = ollama.generate(prompt);
    ostringstream ss;
    ss << "{\"answer\":" << jS(answer) << ",\"model\":" << jS(ollama.genModel)
       << ",\"contexts\":[";
    for (size_t i = 0; i < hits.size(); i++) {
      if (i)
        ss << ',';
      ss << "{\"id\":" << hits[i].second.id
         << ",\"title\":" << jS(hits[i].second.title)
         << ",\"text\":" << jS(hits[i].second.text)
         << ",\"distance\":" << fixed << setprecision(4)
         << hits[i].first << '}';
    }
    ss << "],\"docCount\":" << docDB.size() << '}';
    res.set_content(ss.str(), "application/json");
  });
  svr.Get("/status", [&](const httplib::Request &, httplib::Response &res) {
    cors(res);
    bool up = ollama.isAvailable();
    ostringstream ss;
    ss << "{\"ollamaAvailable\":" << (up ? "true" : "false")
       << ",\"embedModel\":" << jS(ollama.embedModel)
       << ",\"genModel\":" << jS(ollama.genModel)
       << ",\"docCount\":" << docDB.size() << ",\"docDims\":" << docDB.getDims()
       << ",\"demoDims\":" << DIMS << ",\"demoCount\":" << db.size() << '}';
    res.set_content(ss.str(), "application/json");
  });
  svr.Get("/stats", [&](const httplib::Request &, httplib::Response &res) {
    cors(res);
    ostringstream ss;
    ss << "{\"count\":" << db.size() << ",\"dims\":" << DIMS
       << ",\"algorithms\":[\"bruteforce\",\"kdtree\",\"hnsw\"]"
       << ",\"metrics\":[\"euclidean\",\"cosine\",\"manhattan\"]}";
    res.set_content(ss.str(), "application/json");
  });
  svr.Get("/", [](const httplib::Request &, httplib::Response &res) {
    ifstream f("index.html");
    if (!f.is_open()) {
      res.status = 404;
      return;
    }
    res.set_content(string(istreambuf_iterator<char>(f),
                                istreambuf_iterator<char>()),
                    "text/html");
  });
  svr.listen("0.0.0.0", 8080);
  return 0;
}

