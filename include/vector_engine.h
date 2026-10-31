/**
 * The vector search engine: distance metrics, brute force, KD-Tree and HNSW indexes,
 * plus the small JSON and text helpers the server uses. It has no networking
 * dependency, so it can be unit tested on its own.
 */
#ifndef VECTOR_ENGINE_H
#define VECTOR_ENGINE_H

#include <algorithm>
#include <chrono>
#include <climits>
#include <cmath>
#include <functional>
#include <iomanip>
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

inline float euclidean(const vector<float> &a, const vector<float> &b) {
  float s = 0;
  for (int i = 0; i < (int)a.size(); i++) {
    float d = a[i] - b[i];
    s += d * d;
  }
  return sqrt(s);
}

inline float cosine(const vector<float> &a, const vector<float> &b) {
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
inline float manhattan(const vector<float> &a, const vector<float> &b) {
  float s = 0;
  for (int i = 0; i < (int)a.size(); i++)
    s += abs(a[i] - b[i]);
  return s;
}
inline DistFn getDistFn(const string &m) {
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
inline string jS(const string &s) {
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
inline string jVec(const vector<float> &v) {
  ostringstream ss;
  ss << '[';
  for (size_t i = 0; i < v.size(); i++) {
    if (i)
      ss << ',';
    ss << fixed << setprecision(4) << v[i];
  }
  return ss.str() + ']';
}
inline vector<float> parseVec(const string &s) {
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
inline string extractStr(const string &body, const string &key) {
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
inline int extractInt(const string &body, const string &key, int def = 0) {
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
inline bool parseBody(const string &b, string &meta, string &cat,
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

inline vector<string> chunkText(const string &text,
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

#endif
