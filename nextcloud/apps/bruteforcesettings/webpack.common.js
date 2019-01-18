const path = require('path')
const { VueLoaderPlugin } = require('vue-loader');

module.exports = {
  entry: path.join(__dirname, 'src', 'main.js'),
  output: {
    path: path.resolve(__dirname, './js'),
    publicPath: '/js',
    filename: 'bruteforcesettings.js'
  },
  module: {
    rules: [
      {
        test: /\.vue$/,
        loader: 'vue-loader',
      }
    ]
  },
  plugins: [
    new VueLoaderPlugin()
  ],
  resolve: {
    alias: {
      'vue$': 'vue/dist/vue.esm.js'
    },
    extensions: ['*', '.js', '.vue', '.json']
  }
}
